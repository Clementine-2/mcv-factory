from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from project_factory.validator import DEFAULT_BLUEPRINT_SCHEMA, DEFAULT_META_SCHEMA, load_document, validate_blueprint  # noqa: E402


class BlueprintValidatorTests(unittest.TestCase):
    def load(self, relative: str):
        return load_document(ROOT / relative)


    def test_packaged_schema_copies_match_checkpoint_root_schemas(self):
        self.assertEqual(DEFAULT_BLUEPRINT_SCHEMA.read_bytes(), (ROOT / "schemas" / "blueprint.schema.json").read_bytes())
        self.assertEqual(DEFAULT_META_SCHEMA.read_bytes(), (ROOT / "schemas" / "blueprint-meta.schema.json").read_bytes())

    def test_blueprint_schema_is_valid_draft_2020_12(self):
        schema = json.loads((ROOT / "schemas" / "blueprint.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)

    def test_metadata_schema_is_valid_draft_2020_12(self):
        schema = json.loads((ROOT / "schemas" / "blueprint-meta.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)

    def test_all_golden_blueprints_are_usable(self):
        for path in sorted((ROOT / "fixtures" / "golden").glob("*.yaml")):
            with self.subTest(path=path.name):
                result = validate_blueprint(load_document(path))
                self.assertEqual(result.structure_status, "STRUCTURALLY_VALID")
                self.assertEqual(result.readiness_status, "USABLE")
                self.assertEqual(result.issues, ())

    def test_minimal_blueprint_allows_optional_sections_to_be_absent(self):
        result = validate_blueprint(self.load("fixtures/positive/00_minimal.yaml"))
        self.assertEqual(result.structure_status, "STRUCTURALLY_VALID")
        self.assertEqual(result.readiness_status, "USABLE")

    def test_missing_purpose_is_rejected(self):
        result = validate_blueprint(self.load("fixtures/negative/missing_purpose.yaml"))
        self.assertEqual(result.structure_status, "INVALID")
        self.assertIsNone(result.readiness_status)

    def test_empty_work_products_is_rejected(self):
        result = validate_blueprint(self.load("fixtures/negative/empty_work_products.yaml"))
        self.assertEqual(result.structure_status, "INVALID")

    def test_nested_component_is_rejected(self):
        result = validate_blueprint(self.load("fixtures/negative/nested_component.yaml"))
        self.assertEqual(result.structure_status, "INVALID")
        self.assertTrue(any("components" in issue.message for issue in result.issues))

    def test_wrong_type_is_rejected(self):
        result = validate_blueprint(self.load("fixtures/negative/wrong_type.yaml"))
        self.assertEqual(result.structure_status, "INVALID")

    def test_unknown_root_field_is_rejected(self):
        result = validate_blueprint(self.load("fixtures/negative/unknown_root_field.yaml"))
        self.assertEqual(result.structure_status, "INVALID")

    def test_nonblocking_unresolved_can_still_be_usable(self):
        blueprint = self.load("fixtures/positive/00_minimal.yaml")
        meta = self.load("fixtures/positive/meta_usable.yaml")
        result = validate_blueprint(blueprint, meta)
        self.assertEqual(result.structure_status, "STRUCTURALLY_VALID")
        self.assertEqual(result.readiness_status, "USABLE")

    def test_resolution_required_is_reported(self):
        blueprint = self.load("fixtures/positive/00_minimal.yaml")
        meta = self.load("fixtures/positive/meta_needs_resolution.yaml")
        result = validate_blueprint(blueprint, meta)
        self.assertEqual(result.structure_status, "STRUCTURALLY_VALID")
        self.assertEqual(result.readiness_status, "NEEDS_RESOLUTION")

    def test_blocking_unresolved_is_reported(self):
        blueprint = self.load("fixtures/positive/00_minimal.yaml")
        meta = self.load("fixtures/positive/meta_blocked.yaml")
        result = validate_blueprint(blueprint, meta)
        self.assertEqual(result.structure_status, "STRUCTURALLY_VALID")
        self.assertEqual(result.readiness_status, "BLOCKED")

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        return subprocess.run(
            [sys.executable, "-m", "project_factory", *args, "--json"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )

    def test_cli_exit_code_usable_is_zero(self):
        proc = self.run_cli("fixtures/golden/01_tiny_python_tool.yaml")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_cli_exit_code_needs_resolution_is_two(self):
        proc = self.run_cli(
            "fixtures/positive/00_minimal.yaml",
            "--meta",
            "fixtures/positive/meta_needs_resolution.yaml",
        )
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)

    def test_cli_exit_code_blocked_is_three(self):
        proc = self.run_cli(
            "fixtures/positive/00_minimal.yaml",
            "--meta",
            "fixtures/positive/meta_blocked.yaml",
        )
        self.assertEqual(proc.returncode, 3, proc.stdout + proc.stderr)

    def test_cli_exit_code_invalid_is_one(self):
        proc = self.run_cli("fixtures/negative/missing_purpose.yaml")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
