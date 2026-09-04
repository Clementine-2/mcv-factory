from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from project_factory.normalizer import normalize_requirement  # noqa: E402
from project_factory.validator import validate_blueprint  # noqa: E402


class RequirementNormalizerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = yaml.safe_load((ROOT / "fixtures" / "normalization" / "cases.yaml").read_text(encoding="utf-8"))["cases"]

    def case(self, case_id: str):
        return next(item for item in self.cases if item["id"] == case_id)

    def test_fixture_cases_match_expected_readiness_and_core_facts(self):
        for case in self.cases:
            with self.subTest(case=case["id"]):
                result = normalize_requirement(case["text"])
                self.assertEqual(result.validation.structure_status, "STRUCTURALLY_VALID")
                self.assertEqual(result.validation.readiness_status, case["readiness"])
                kinds = [item["kind"] for item in result.blueprint["work_products"]]
                self.assertEqual(kinds, case["work_products"])

                required = result.blueprint.get("technology", {}).get("required", [])
                self.assertEqual(required, case.get("required_technology", []))

                for forbidden in case.get("forbidden_root_keys", []):
                    self.assertNotIn(forbidden, result.blueprint)
                for forbidden in case.get("forbidden_work_products", []):
                    self.assertNotIn(forbidden, kinds)

    def test_tiny_cli_preserves_hard_no_overwrite_constraint(self):
        result = normalize_requirement(self.case("tiny_python_cli")["text"])
        hard = result.blueprint["constraints"]["hard"]
        self.assertTrue(any("不能覆盖原始文件" in item for item in hard))
        self.assertEqual(result.blueprint["scope"]["scale_hint"], "tiny")
        self.assertEqual(result.metadata["provenance"]["/scope/scale_hint"]["source"], "INFERRED")
        self.assertTrue(result.metadata.get("assumptions"))

    def test_browser_extension_does_not_treat_llm_api_as_service_or_model_product(self):
        result = normalize_requirement(self.case("browser_extension")["text"])
        kinds = {item["kind"] for item in result.blueprint["work_products"]}
        self.assertEqual(kinds, {"browser-extension"})
        self.assertEqual(result.blueprint["lifecycle"], {"stage": "prototype", "horizon": "long-lived"})
        quality = {item["attribute"]: item["level"] for item in result.blueprint["constraints"]["quality"]}
        self.assertEqual(quality["privacy"], "high")

    def test_web_api_extracts_multiple_products_and_quality_without_components(self):
        result = normalize_requirement(self.case("web_api")["text"])
        self.assertEqual([item["kind"] for item in result.blueprint["work_products"]], ["web-ui", "service"])
        self.assertNotIn("components", result.blueprint)
        quality = {item["attribute"]: item["level"] for item in result.blueprint["constraints"]["quality"]}
        self.assertEqual(quality["security"], "high")
        self.assertEqual(quality["reliability"], "high")

    def test_research_request_does_not_invent_build_release_or_model_product(self):
        result = normalize_requirement(self.case("research")["text"])
        kinds = [item["kind"] for item in result.blueprint["work_products"]]
        self.assertEqual(kinds, ["notebook", "experiment", "research-result"])
        self.assertNotIn("model", kinds)
        serialized = json.dumps(result.blueprint, ensure_ascii=False).casefold()
        for forbidden in ("build", "release", "runner", "harness", "pytest"):
            self.assertNotIn(forbidden, serialized)

    def test_large_system_stays_flat_in_normalization_poc(self):
        result = normalize_requirement(self.case("large_system")["text"])
        self.assertEqual(result.blueprint["scope"]["scale_hint"], "large")
        self.assertNotIn("components", result.blueprint)
        quality = {item["attribute"] for item in result.blueprint["constraints"]["quality"]}
        self.assertTrue({"portability", "reliability", "backward-compatibility"}.issubset(quality))

    def test_mobile_without_platform_asks_exactly_one_material_question(self):
        result = normalize_requirement(self.case("ambiguous_mobile")["text"])
        self.assertEqual(result.validation.readiness_status, "NEEDS_RESOLUTION")
        self.assertEqual(len(result.questions), 1)
        self.assertIn("platform", result.questions[0].casefold())
        self.assertTrue(any(item["path"] == "/targets" and item["resolution_required"] for item in result.metadata["unresolved"]))

    def test_generic_app_is_not_guessed_as_web_mobile_or_desktop(self):
        result = normalize_requirement(self.case("ambiguous_app")["text"])
        self.assertEqual(result.blueprint["work_products"], [{"kind": "application"}])
        self.assertEqual(result.validation.readiness_status, "NEEDS_RESOLUTION")
        self.assertEqual(len(result.questions), 1)

    def test_unspecified_project_is_not_filled_with_fake_defaults(self):
        result = normalize_requirement(self.case("unspecified_project")["text"])
        self.assertEqual(result.blueprint["work_products"], [{"kind": "unspecified"}])
        for forbidden in ("targets", "technology", "lifecycle", "scope", "constraints", "components", "extensions"):
            self.assertNotIn(forbidden, result.blueprint)
        self.assertEqual(result.validation.readiness_status, "NEEDS_RESOLUTION")

    def test_provider_names_do_not_leak_into_blueprint_structure(self):
        result = normalize_requirement(self.case("provider_names_do_not_leak")["text"])
        # The raw request is intentionally retained in project.purpose, so provider names
        # may remain there as user text. They must not become structured Blueprint fields.
        self.assertIn("Codex", result.blueprint["project"]["purpose"])
        self.assertIn("Dagu", result.blueprint["project"]["purpose"])
        self.assertEqual(set(result.blueprint), {"schema_version", "project", "work_products", "technology"})
        self.assertEqual(result.blueprint["technology"]["required"], ["python"])
        self.assertEqual(result.blueprint["work_products"], [{"kind": "cli"}])

    def test_common_chinese_security_and_testability_quality_are_extracted(self):
        result = normalize_requirement("做一个 Python 命令行工具，要求安全、可测试，不能覆盖原文件。")
        quality = {item["attribute"]: item["level"] for item in result.blueprint["constraints"]["quality"]}
        self.assertIn("security", quality)
        self.assertIn("testability", quality)
        self.assertIn("不能覆盖原文件", " ".join(result.blueprint["constraints"]["hard"]))

    def test_missing_optional_facts_do_not_create_questions(self):
        result = normalize_requirement("做一个 Python 命令行工具。")
        self.assertEqual(result.validation.readiness_status, "USABLE")
        self.assertEqual(result.questions, ())
        self.assertNotIn("lifecycle", result.blueprint)
        self.assertNotIn("scope", result.blueprint)
        self.assertNotIn("constraints", result.blueprint)

    def test_technology_preference_and_prohibition_are_not_promoted_to_required(self):
        result = normalize_requirement("做一个命令行工具，最好用 Python，禁止 Electron。")
        self.assertEqual(result.blueprint["technology"]["preferred"], ["python"])
        self.assertEqual(result.blueprint["technology"]["prohibited"], ["electron"])
        self.assertNotIn("required", result.blueprint["technology"])

    def test_all_emitted_provenance_classes_are_allowed_and_text_poc_emits_no_detected_or_default(self):
        for case in self.cases:
            result = normalize_requirement(case["text"])
            sources = {record["source"] for record in result.metadata.get("provenance", {}).values()}
            self.assertTrue(sources.issubset({"EXPLICIT", "INFERRED"}))
            self.assertNotIn("DETECTED", sources)
            self.assertNotIn("DEFAULT", sources)

    def test_output_round_trip_passes_existing_validator(self):
        result = normalize_requirement(self.case("browser_extension")["text"])
        validated = validate_blueprint(result.blueprint, result.metadata)
        self.assertEqual(validated.structure_status, "STRUCTURALLY_VALID")
        self.assertEqual(validated.readiness_status, "USABLE")

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        return subprocess.run(
            [sys.executable, "-m", "project_factory", *args],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=30,
        )

    def test_normalize_cli_writes_round_trippable_blueprint_and_meta(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = self.run_cli(
                "normalize",
                self.case("browser_extension")["text"],
                "--out-dir",
                tmp,
                "--json",
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["validation"]["readiness_status"], "USABLE")
            blueprint_path = Path(tmp) / "project.blueprint.yaml"
            meta_path = Path(tmp) / "project.blueprint.meta.yaml"
            self.assertTrue(blueprint_path.exists())
            self.assertTrue(meta_path.exists())

            validate_proc = self.run_cli("validate", str(blueprint_path), "--meta", str(meta_path), "--json")
            self.assertEqual(validate_proc.returncode, 0, validate_proc.stdout + validate_proc.stderr)

    def test_normalize_cli_returns_two_for_needs_resolution(self):
        proc = self.run_cli("normalize", self.case("ambiguous_mobile")["text"], "--json")
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["validation"]["readiness_status"], "NEEDS_RESOLUTION")
        self.assertEqual(len(payload["questions"]), 1)

    def test_secret_like_material_is_redacted_from_persisted_purpose(self):
        secret = "sk-REDACTED_TEST_FIXTURE"
        result = normalize_requirement(f"做一个 Python CLI，API_KEY={secret}。")
        self.assertNotIn(secret, result.blueprint["project"]["purpose"])
        self.assertIn("[REDACTED_SECRET]", result.blueprint["project"]["purpose"])
        note = result.metadata["provenance"]["/project/purpose"].get("note", "")
        self.assertIn("redacted", note.casefold())
        serialized = json.dumps(result.to_dict(), ensure_ascii=False)
        self.assertNotIn(secret, serialized)

    def test_empty_requirement_is_rejected(self):
        with self.assertRaises(ValueError):
            normalize_requirement("   ")


if __name__ == "__main__":
    unittest.main()
