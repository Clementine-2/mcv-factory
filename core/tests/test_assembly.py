from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from project_factory.assembly import AssemblyOptions, plan_assembly
from project_factory.factory import FactoryError, generate_project
from project_factory.harness import resolve_harnesses
from project_factory.template import blueprint_from_template, empty_template, export_template


class AssemblyPlanTests(unittest.TestCase):
    def test_web_and_service_are_split_not_a_welded_profile(self) -> None:
        blueprint = {
            "schema_version": "0.1",
            "project": {"purpose": "split"},
            "work_products": [{"kind": "http-service"}, {"kind": "web-spa"}],
            "technology": {"required": ["python", "react"]},
        }
        plan = plan_assembly(blueprint, "shop")
        self.assertEqual(plan.mode, "split")
        self.assertEqual(plan.profile_id, "frontend-backend-split")
        self.assertEqual(plan.packages[0].directory, "api")
        self.assertEqual(plan.packages[1].directory, "web")

    def test_cli_plus_library_is_refused_instead_of_silent_drop(self) -> None:
        blueprint = {
            "schema_version": "0.1",
            "project": {"purpose": "two products"},
            "work_products": [{"kind": "cli"}, {"kind": "library"}],
            "technology": {"required": ["python"]},
        }
        plan = plan_assembly(blueprint, "mixed")
        self.assertEqual(plan.mode, "reject")
        self.assertIn("silently drop", plan.reason)

    def test_split_branch_refuses_extra_product_instead_of_silent_drop(self) -> None:
        # Case C: web + service + a third product must NOT be silently split-and-dropped.
        blueprint = {
            "schema_version": "0.1",
            "project": {"purpose": "web + api + notebook"},
            "work_products": [
                {"kind": "web-spa"},
                {"kind": "http-service"},
                {"kind": "notebook"},
            ],
            "technology": {"required": ["python", "typescript"]},
        }
        plan = plan_assembly(blueprint, "shop")
        self.assertEqual(plan.mode, "reject")
        self.assertIn("notebook", plan.reason)

    def test_split_branch_refuses_second_web_instead_of_silent_drop(self) -> None:
        # A second web product alongside web + service is also an extra to be dropped.
        blueprint = {
            "schema_version": "0.1",
            "project": {"purpose": "two webs + api"},
            "work_products": [
                {"kind": "web-spa"},
                {"kind": "web-ui"},
                {"kind": "http-service"},
            ],
            "technology": {"required": ["python", "typescript"]},
        }
        plan = plan_assembly(blueprint, "shop")
        self.assertEqual(plan.mode, "reject")
        self.assertIn("web-ui", plan.reason)

    def test_clean_web_service_split_still_passes(self) -> None:
        blueprint = {
            "schema_version": "0.1",
            "project": {"purpose": "split"},
            "work_products": [{"kind": "http-service"}, {"kind": "web-spa"}],
            "technology": {"required": ["python", "react"]},
        }
        plan = plan_assembly(blueprint, "shop")
        self.assertEqual(plan.mode, "split")


class OptionalLayersTests(unittest.TestCase):
    def test_nothing_selected_creates_empty_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result = generate_project(
                "",
                "empty-home",
                Path(temp),
                options=AssemblyOptions(False, False, False, False, False, ()),
            )
            root = result.project_root
            self.assertTrue(root.is_dir())
            self.assertEqual([path for path in root.rglob("*") if path.is_file()], [])
            self.assertEqual(result.verification["status"], "BLANK")
            self.assertFalse((root / "AGENTS.md").exists())
            self.assertFalse((root / "project.lock.json").exists())

    def test_harness_can_be_omitted(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result = generate_project(
                "做一个 Python library，提供可复用的文本标准化能力。",
                "no-harness-lib",
                Path(temp),
                options=AssemblyOptions(harness=False, harness_ids=()),
            )
            self.assertFalse((result.project_root / "AGENTS.md").exists())
            self.assertFalse((result.project_root / "CLAUDE.md").exists())
            self.assertTrue((result.project_root / "pyproject.toml").is_file())

    def test_empty_harness_list_is_allowed(self) -> None:
        self.assertEqual(resolve_harnesses(()), ())


class TemplateTests(unittest.TestCase):
    def test_export_and_fill_round_trip(self) -> None:
        payload = empty_template()
        payload["project_name"] = "shop"
        payload["purpose"] = "web plus api"
        payload["work_products"] = ["http-service", "web-spa"]
        payload["language"] = "python"
        payload["body"] = "react"
        payload["repo"] = "frontend-backend-split"
        blueprint = blueprint_from_template(payload)
        kinds = {item["kind"] for item in blueprint["work_products"]}
        self.assertIn("http-service", kinds)
        self.assertIn("web-spa", kinds)

    def test_export_writes_ai_instructions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "template.yaml"
            payload = export_template(path)
            self.assertTrue(path.is_file())
            self.assertIn("Do not invent work_product kinds", payload["ai_instructions"])

    def test_template_cli_export_exits_zero(self) -> None:
        from project_factory.ux import main as ux_main

        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "t.yaml"
            self.assertEqual(ux_main(["template", "export", "-o", str(path)]), 0)
            self.assertTrue(path.is_file())


class SplitGenerateTests(unittest.TestCase):
    def test_natural_language_fastapi_react_assembles_two_packages(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result = generate_project(
                "做一个 FastAPI 后端和 React 单页应用。",
                "shop-board",
                Path(temp),
            )
            self.assertEqual(result.profile.profile_id, "frontend-backend-split")
            self.assertTrue((result.project_root / "api" / "pyproject.toml").is_file())
            self.assertTrue((result.project_root / "web" / "package.json").is_file())
            self.assertTrue(result.verification["required_gates_passed"])
            self.assertTrue((result.project_root / "skills" / "python-http-service" / "SKILL.md").is_file())
            self.assertTrue((result.project_root / "skills" / "typescript-web-react" / "SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
