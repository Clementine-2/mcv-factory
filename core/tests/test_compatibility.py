from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from project_factory.compatibility import (
    CandidateObservation,
    CompatibilityError,
    CompatibilitySubject,
    build_status_report,
    evaluate_observation,
    load_compatibility_registry,
    load_observations,
    promotion_proposal,
    run_local_provider_lab,
    runtime_requirements_match,
)
from project_factory.registry import RegistryError, inspect_provider, load_registry


ROOT = Path(__file__).resolve().parents[1]
OBSERVATION = ROOT / "compatibility" / "observations" / "2026-08-30.yaml"


class CompatibilityRegistryTests(unittest.TestCase):
    def test_registry_has_current_external_subjects(self) -> None:
        subjects = load_compatibility_registry()
        self.assertEqual(set(subjects), {"uv", "npm", "spec-kit", "codex", "claude"})
        self.assertEqual(subjects["uv"].supported_versions, ("0.10.0",))
        self.assertEqual(subjects["npm"].supported_versions, ("10.9.2",))
        self.assertEqual(subjects["spec-kit"].supported_versions, ())
        self.assertEqual(subjects["spec-kit"].supported_contract_versions, ("1.0.1",))

    def test_supported_versions_must_be_tested(self) -> None:
        content = '''schema_version: "0.1"\nsubjects:\n  - id: demo\n    kind: provider\n    adapter_version: "0.1"\n    supported_versions: ["2.0.0"]\n    tested_versions: ["1.0.0"]\n    required_checks: [version-probe]\n'''
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "compat.yaml"
            path.write_text(content, encoding="utf-8")
            with self.assertRaisesRegex(CompatibilityError, "must also be tested"):
                load_compatibility_registry(path)

    def test_observation_is_dynamic_evidence_not_registry_state(self) -> None:
        observations = load_observations(OBSERVATION)
        self.assertEqual(len(observations), 6)
        uv = next(item for item in observations if item.subject == "uv")
        self.assertEqual(uv.observed_latest, "0.12.7")
        self.assertEqual(uv.version, "0.12.7")


class RuntimeRequirementTests(unittest.TestCase):
    def test_npm_12_is_incompatible_with_observed_node_22_16(self) -> None:
        obs = next(
            item for item in load_observations(OBSERVATION)
            if item.subject == "npm" and item.version == "12.0.2"
        )
        ok, failures = runtime_requirements_match(obs.runtime_requirements, {"node": "22.16.0"})
        self.assertFalse(ok)
        self.assertTrue(failures)

    def test_npm_10_9_9_is_compatible_with_node_22_16(self) -> None:
        obs = next(
            item for item in load_observations(OBSERVATION)
            if item.subject == "npm" and item.version == "10.9.9"
        )
        ok, failures = runtime_requirements_match(obs.runtime_requirements, {"node": "22.16.0"})
        self.assertTrue(ok)
        self.assertEqual(failures, [])

    def test_missing_runtime_is_visible_failure(self) -> None:
        requirements = {"node": {"any_of": [{"min": "20.0.0"}]}}
        ok, failures = runtime_requirements_match(requirements, {})
        self.assertFalse(ok)
        self.assertIn("unavailable", failures[0])


class ObservationEvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.subjects = load_compatibility_registry()
        self.observations = load_observations(OBSERVATION)

    def candidate(self, subject: str, version: str) -> CandidateObservation:
        return next(item for item in self.observations if item.subject == subject and item.version == version)

    def test_uv_latest_stays_pending_without_candidate_artifact(self) -> None:
        result = evaluate_observation(
            self.candidate("uv", "0.12.7"), self.subjects["uv"],
            runtime_versions={"node": "22.16.0"}, locally_available_version="0.10.0"
        )
        self.assertEqual(result["state"], "PENDING")
        self.assertEqual(result["reason"], "CANDIDATE_ARTIFACT_UNAVAILABLE")

    def test_npm_latest_rejected_by_runtime_before_artifact_availability(self) -> None:
        result = evaluate_observation(
            self.candidate("npm", "12.0.2"), self.subjects["npm"],
            runtime_versions={"node": "22.16.0"}, locally_available_version="10.9.2"
        )
        self.assertEqual(result["state"], "REJECTED")
        self.assertEqual(result["reason"], "RUNTIME_INCOMPATIBLE")

    def test_runtime_compatible_npm_line_is_pending_until_artifact_tested(self) -> None:
        result = evaluate_observation(
            self.candidate("npm", "10.9.9"), self.subjects["npm"],
            runtime_versions={"node": "22.16.0"}, locally_available_version="10.9.2"
        )
        self.assertEqual(result["state"], "PENDING")
        self.assertTrue(result["runtime_compatible"])

    def test_supported_version_wins_over_candidate_state(self) -> None:
        obs = CandidateObservation(
            subject="uv", version="0.10.0", observed_latest="0.12.7",
            source_kind="test", source="fixture", published_at=None,
            runtime_requirements={}, note=None,
        )
        result = evaluate_observation(
            obs, self.subjects["uv"], runtime_versions={}, locally_available_version="0.10.0"
        )
        self.assertEqual(result["state"], "SUPPORTED")

    def test_contract_supported_runtime_unverified_is_not_promoted_to_runtime_supported(self) -> None:
        result = evaluate_observation(
            self.candidate("spec-kit", "1.0.1"), self.subjects["spec-kit"],
            runtime_versions={"node": "22.16.0"}, locally_available_version=None
        )
        self.assertEqual(result["state"], "CONTRACT_SUPPORTED")
        self.assertEqual(result["reason"], "RUNTIME_UNVERIFIED")

    def test_status_report_keeps_latest_separate_from_supported(self) -> None:
        report = build_status_report(
            ROOT / "src" / "project_factory" / "registry_data" / "compatibility.yaml",
            OBSERVATION,
            runtime_versions={"node": "22.16.0"},
            local_versions={"uv": "0.10.0", "npm": "10.9.2", "spec-kit": None, "codex": None, "claude": None},
        )
        uv = next(item for item in report["candidates"] if item["subject"] == "uv")
        self.assertEqual(uv["observed_latest"], "0.12.7")
        self.assertEqual(uv["state"], "PENDING")
        self.assertEqual(tuple(report["subjects"]["uv"]["supported_versions"]), ("0.10.0",))


class PromotionTests(unittest.TestCase):
    def test_fully_tested_candidate_can_only_produce_non_automatic_proposal(self) -> None:
        subject = CompatibilitySubject(
            id="demo", kind="provider", adapter_version="0.1",
            supported_versions=("1.0.0",), tested_versions=("1.0.0",),
            supported_contract_versions=(), required_checks=("version-probe",),
        )
        report = {
            "state": "TESTED", "promotion_eligible": True, "version": "1.1.0", "failed_checks": []
        }
        proposal = promotion_proposal(subject, report)
        self.assertEqual(proposal["from"], "TESTED")
        self.assertEqual(proposal["to"], "SUPPORTED")
        self.assertFalse(proposal["automatic_apply"])
        self.assertTrue(proposal["required_human_or_release_gate"])

    def test_incomplete_candidate_cannot_be_promoted(self) -> None:
        subject = load_compatibility_registry()["uv"]
        with self.assertRaisesRegex(CompatibilityError, "fully TESTED"):
            promotion_proposal(subject, {"state": "REJECTED", "promotion_eligible": False, "version": "0.12.7"})


class ProviderRegistryGateTests(unittest.TestCase):
    def test_generation_reports_unsupported_version_without_blocking(self) -> None:
        # T23: the version gate is removed. A version that is tested but not in the
        # supported list must NOT raise — it is reported as SUPPORTED (it is tested)
        # and generation proceeds.
        registry = load_registry()
        spec = registry.providers["uv"]
        tested_only = spec.__class__(
            id=spec.id,
            version=spec.version,
            capability=spec.capability,
            executable=spec.executable,
            version_args=spec.version_args,
            version_regex=spec.version_regex,
            tested_versions=("0.10.0", "0.11.0"),
            supported_versions=("0.10.0",),
            integration=spec.integration,
            upstream_source_modified=spec.upstream_source_modified,
        )
        completed = mock.Mock(returncode=0, stdout="uv 0.11.0\n", stderr="")
        with mock.patch("project_factory.registry.shutil.which", return_value="/fake/uv"):
            with mock.patch("project_factory.registry.subprocess.run", return_value=completed):
                runtime = inspect_provider(tested_only)
        self.assertEqual(runtime.version, "0.11.0")
        self.assertEqual(runtime.version_status, "SUPPORTED")


class LabMechanismTests(unittest.TestCase):
    def test_lab_rejects_failed_probe_without_claiming_tested(self) -> None:
        subject = load_compatibility_registry()["uv"]
        with mock.patch("project_factory.compatibility.shutil.which", return_value=None):
            report = run_local_provider_lab(
                subject, executable="uv", version_args=("--version",), version_regex=r"(\d+\.\d+\.\d+)"
            )
        self.assertEqual(report["state"], "PENDING")
        self.assertEqual(report["reason"], "CANDIDATE_ARTIFACT_UNAVAILABLE")
        self.assertFalse(report["promotion_eligible"])
        self.assertIn("version-probe", report["failed_checks"])


if __name__ == "__main__":
    unittest.main()
