from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from project_factory.decision import DecisionError, IntentSnapshot, RepositoryState, evaluate_decision, main as decision_main


ROOT = Path(__file__).resolve().parents[1]


def blueprint(*, scale: str | None = None, quality: str | None = None, components: bool = False):
    value = {
        "schema_version": "0.1",
        "project": {"purpose": "decision test"},
        "work_products": [{"kind": "cli"}],
    }
    if scale:
        value["scope"] = {"scale_hint": scale}
    if quality:
        value["constraints"] = {"quality": [{"attribute": "reliability", "level": quality}]}
    if components:
        value["components"] = [
            {"id": "core", "purpose": "core", "work_products": [{"kind": "library"}]}
        ]
    return value


class DecisionKernelTests(unittest.TestCase):
    def test_bootstrap_default_is_small_single_agent_and_evidence_required(self) -> None:
        result = evaluate_decision(blueprint())
        decision = result.decision
        self.assertEqual(decision.materialization, "minimal")
        self.assertEqual(decision.verification_depth, "baseline")
        self.assertEqual(decision.agent_topology, "single-main-agent")
        self.assertEqual(decision.parallelism, 1)
        self.assertFalse(decision.reviewer_required)
        self.assertFalse(decision.runner_required)
        self.assertTrue(decision.evidence_required)

    def test_large_project_does_not_make_low_risk_documentation_change_high_risk(self) -> None:
        result = evaluate_decision(
            blueprint(scale="large", components=True),
            intent=IntentSnapshot(kind="documentation", change_scope="local", risk="low"),
            repository=RepositoryState(existing_project=True, clean_worktree=True),
        )
        self.assertEqual(result.decision.materialization, "standard")
        self.assertEqual(result.decision.verification_depth, "baseline")
        self.assertFalse(result.decision.reviewer_required)
        self.assertEqual(result.decision.isolation, "none")

    def test_critical_quality_requires_strict_verification_and_review(self) -> None:
        result = evaluate_decision(blueprint(quality="critical"))
        self.assertEqual(result.decision.verification_depth, "strict")
        self.assertTrue(result.decision.reviewer_required)

    def test_high_risk_existing_refactor_requests_isolation_and_checkpoint(self) -> None:
        result = evaluate_decision(
            blueprint(),
            intent=IntentSnapshot(kind="refactor", change_scope="cross-module", risk="high"),
            repository=RepositoryState(existing_project=True, clean_worktree=True),
        )
        self.assertEqual(result.decision.verification_depth, "elevated")
        self.assertTrue(result.decision.reviewer_required)
        self.assertEqual(result.decision.checkpoint_policy, "before-and-after-change")
        self.assertEqual(result.decision.isolation, "isolated-worktree")

    def test_long_running_request_requests_runner_once_capability_is_available(self) -> None:
        result = evaluate_decision(
            blueprint(),
            intent=IntentSnapshot(kind="investigation", change_scope="local", risk="normal", autonomy="long-running"),
        )
        self.assertTrue(result.decision.runner_required)
        self.assertTrue(any("long-running autonomy requests a runner capability" in item for item in result.trace))
        self.assertFalse(any("runner request suppressed" in item for item in result.trace))

    def test_registry_formula_and_policy_are_recorded(self) -> None:
        result = evaluate_decision(blueprint())
        self.assertEqual(result.formulas[0]["id"], "baseline-engineering")
        self.assertEqual(result.policies[0]["id"], "safe-defaults")

    def test_invalid_intent_is_rejected(self) -> None:
        with self.assertRaisesRegex(DecisionError, "Unsupported intent kind"):
            evaluate_decision(blueprint(), intent=IntentSnapshot(kind="make-it-awesome"))

    def test_decision_rejects_structurally_invalid_blueprint(self) -> None:
        with self.assertRaisesRegex(DecisionError, "structurally invalid"):
            evaluate_decision({"schema_version": "0.1", "project": {"purpose": "x"}, "work_products": []})

    def test_decide_cli_emits_context_and_no_execution_side_effect(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "blueprint.yaml"
            path.write_text(
                "schema_version: '0.1'\nproject:\n  purpose: test\nwork_products:\n  - kind: cli\n",
                encoding="utf-8",
            )
            from contextlib import redirect_stdout
            stream = io.StringIO()
            with redirect_stdout(stream):
                returncode = decision_main([str(path), "--kind", "refactor", "--risk", "high", "--existing-project"])
            self.assertEqual(returncode, 0)
            payload = json.loads(stream.getvalue())
            self.assertEqual(payload["context"]["intent"]["kind"], "refactor")
            self.assertEqual(payload["decision"]["isolation"], "isolated-worktree")


if __name__ == "__main__":
    unittest.main()
