from __future__ import annotations

import io
import json
import unittest
from pathlib import Path

from project_factory.semantic import (
    SemanticAdapterError,
    SemanticProposal,
    SemanticSupport,
    UserConfirmedSemanticAdapter,
    run_semantic_intake,
    main as semantic_main,
)


ROOT = Path(__file__).resolve().parents[1]


class _ExternalAdapter:
    id = "fixture-llm-adapter"
    version = "0.1"
    trust_class = "external-semantic"

    def __init__(self, proposal: SemanticProposal):
        self._proposal = proposal

    def propose(self, text: str) -> SemanticProposal:
        return self._proposal


class SemanticIntakeTests(unittest.TestCase):
    def test_default_adapter_preserves_deterministic_baseline_and_records_receipt(self) -> None:
        result = run_semantic_intake("做一个 Python 命令行工具，不能覆盖原始文件。")
        self.assertEqual(result.validation.readiness_status, "USABLE")
        self.assertEqual(result.receipt["adapter"]["id"], "deterministic-baseline")
        self.assertEqual(result.receipt["guard"]["status"], "PASS")
        self.assertIn("python", result.blueprint["technology"]["required"])
        self.assertEqual(result.blueprint["work_products"][0]["kind"], "cli")

    def test_compliant_external_semantic_adapter_requires_auditable_support(self) -> None:
        text = "Build a Python CLI for local text cleanup."
        proposal = SemanticProposal(
            blueprint={
                "schema_version": "0.1",
                "project": {"purpose": text},
                "work_products": [{"kind": "cli"}],
                "technology": {"required": ["python"]},
            },
            metadata={
                "schema_version": "0.1",
                "provenance": {
                    "/project/purpose": {"source": "EXPLICIT"},
                    "/work_products/0/kind": {"source": "INFERRED"},
                    "/technology/required/0": {"source": "EXPLICIT"},
                },
            },
            support=(
                SemanticSupport("/project/purpose", "EXPLICIT", evidence_text=text),
                SemanticSupport(
                    "/work_products/0/kind",
                    "INFERRED",
                    evidence_text="CLI",
                    reason="The request explicitly asks for a command-line deliverable.",
                ),
                SemanticSupport("/technology/required/0", "EXPLICIT", evidence_text="Python"),
            ),
        )
        result = run_semantic_intake(text, _ExternalAdapter(proposal))
        self.assertEqual(result.validation.readiness_status, "USABLE")
        self.assertEqual(result.receipt["adapter"]["trust_class"], "external-semantic")
        self.assertEqual(len(result.receipt["support"]), 3)

    def test_external_explicit_claim_without_source_evidence_is_rejected(self) -> None:
        text = "Build a CLI."
        proposal = SemanticProposal(
            blueprint={
                "schema_version": "0.1",
                "project": {"purpose": text},
                "work_products": [{"kind": "cli"}],
                "technology": {"required": ["rust"]},
            },
            metadata={
                "schema_version": "0.1",
                "provenance": {
                    "/project/purpose": {"source": "EXPLICIT"},
                    "/work_products/0/kind": {"source": "INFERRED"},
                    "/technology/required/0": {"source": "EXPLICIT"},
                },
            },
            support=(
                SemanticSupport("/project/purpose", "EXPLICIT", evidence_text=text),
                SemanticSupport("/work_products/0/kind", "INFERRED", evidence_text="CLI", reason="CLI wording"),
                SemanticSupport("/technology/required/0", "EXPLICIT", evidence_text="Rust"),
            ),
        )
        with self.assertRaisesRegex(SemanticAdapterError, "not present"):
            run_semantic_intake(text, _ExternalAdapter(proposal))

    def test_text_only_external_adapter_cannot_claim_detected_repository_fact(self) -> None:
        text = "Build a Python CLI."
        proposal = SemanticProposal(
            blueprint={
                "schema_version": "0.1",
                "project": {"purpose": text},
                "work_products": [{"kind": "cli"}],
            },
            metadata={
                "schema_version": "0.1",
                "provenance": {
                    "/project/purpose": {"source": "DETECTED"},
                    "/work_products/0/kind": {"source": "INFERRED"},
                },
            },
            support=(
                SemanticSupport("/project/purpose", "DETECTED"),
                SemanticSupport("/work_products/0/kind", "INFERRED", evidence_text="CLI", reason="CLI wording"),
            ),
        )
        with self.assertRaisesRegex(SemanticAdapterError, "may not claim DETECTED"):
            run_semantic_intake(text, _ExternalAdapter(proposal))

    def test_structured_provider_leakage_is_still_rejected_by_blueprint_schema(self) -> None:
        text = "Build a Python CLI with Codex."
        proposal = SemanticProposal(
            blueprint={
                "schema_version": "0.1",
                "project": {"purpose": text},
                "work_products": [{"kind": "cli"}],
                "provider": "codex",
            },
            metadata={
                "schema_version": "0.1",
                "provenance": {
                    "/project/purpose": {"source": "EXPLICIT"},
                    "/work_products/0/kind": {"source": "INFERRED"},
                },
            },
            support=(
                SemanticSupport("/project/purpose", "EXPLICIT", evidence_text=text),
                SemanticSupport("/work_products/0/kind", "INFERRED", evidence_text="CLI", reason="CLI wording"),
            ),
        )
        result = run_semantic_intake(text, _ExternalAdapter(proposal))
        self.assertEqual(result.validation.structure_status, "INVALID")



    def test_external_adapter_never_receives_raw_secret_material(self) -> None:
        secret = "sk-REDACTED_TEST_FIXTURE"
        seen: list[str] = []

        class CapturingAdapter:
            id = "capture"
            version = "0.1"
            trust_class = "external-semantic"

            def propose(self, text: str) -> SemanticProposal:
                seen.append(text)
                return SemanticProposal(
                    blueprint={
                        "schema_version": "0.1",
                        "project": {"purpose": text},
                        "work_products": [{"kind": "cli"}],
                    },
                    metadata={
                        "schema_version": "0.1",
                        "provenance": {
                            "/project/purpose": {"source": "EXPLICIT"},
                            "/work_products/0/kind": {"source": "INFERRED"},
                        },
                    },
                    support=(
                        SemanticSupport("/project/purpose", "EXPLICIT", evidence_text=text),
                        SemanticSupport(
                            "/work_products/0/kind",
                            "INFERRED",
                            evidence_text="CLI",
                            reason="The user explicitly requested a CLI.",
                        ),
                    ),
                )

        result = run_semantic_intake(f"Build a Python CLI. API_KEY={secret}", CapturingAdapter())
        self.assertEqual(len(seen), 1)
        self.assertNotIn(secret, seen[0])
        self.assertIn("[REDACTED_SECRET]", seen[0])
        self.assertGreaterEqual(result.receipt["guard"]["secret_redactions"], 1)

    def test_user_confirmed_adapter_still_runs_schema_and_readiness_gates(self) -> None:
        blueprint = {
            "schema_version": "0.1",
            "project": {"purpose": "Confirmed Python CLI"},
            "work_products": [{"kind": "cli"}],
            "technology": {"required": ["python"]},
        }
        result = run_semantic_intake(
            "Build a tool",
            UserConfirmedSemanticAdapter(blueprint, {"schema_version": "0.1"}),
        )
        self.assertEqual(result.receipt["adapter"]["trust_class"], "user-confirmed")
        self.assertEqual(result.validation.readiness_status, "USABLE")

    def test_intake_cli_records_adapter_receipt(self) -> None:
        from contextlib import redirect_stdout
        stream = io.StringIO()
        with redirect_stdout(stream):
            returncode = semantic_main(["做一个 Python 命令行工具。", "--json"])
        self.assertEqual(returncode, 0)
        payload = json.loads(stream.getvalue())
        self.assertEqual(payload["receipt"]["adapter"]["id"], "deterministic-baseline")
        self.assertEqual(payload["validation"]["readiness_status"], "USABLE")

    def test_secret_material_is_redacted_even_if_external_adapter_echoes_it(self) -> None:
        secret = "sk-REDACTED_TEST_FIXTURE"
        text = f"Build a Python CLI. API_KEY={secret}"
        proposal = SemanticProposal(
            blueprint={
                "schema_version": "0.1",
                "project": {"purpose": text},
                "work_products": [{"kind": "cli"}],
            },
            metadata={
                "schema_version": "0.1",
                "provenance": {
                    "/project/purpose": {"source": "EXPLICIT"},
                    "/work_products/0/kind": {"source": "INFERRED"},
                },
            },
            support=(
                SemanticSupport("/project/purpose", "EXPLICIT", evidence_text=text),
                SemanticSupport("/work_products/0/kind", "INFERRED", evidence_text="CLI", reason="CLI wording"),
            ),
        )
        result = run_semantic_intake(text, _ExternalAdapter(proposal))
        serialized = str(result.to_dict())
        self.assertNotIn(secret, serialized)
        self.assertIn("[REDACTED_SECRET]", serialized)


if __name__ == "__main__":
    unittest.main()
