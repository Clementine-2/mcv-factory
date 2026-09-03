from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from project_factory.factory import FACTORY_VERSION, generate_project
from project_factory.overlay import (
    ANSWERS_RELATIVE,
    OVERLAY_MANAGED_PATHS,
    SKILL_RELATIVE,
    SPINE_RELATIVE,
    OverlayError,
    apply_factory_overlay,
    destination_is_forbidden,
    render_overlay_targets,
)
from project_factory.upgrade import apply_upgrade, plan_upgrade


class OverlayPluginTests(unittest.TestCase):
    def test_render_is_allowlisted_and_excludes_source_trees(self) -> None:
        targets = render_overlay_targets(
            project_name="demo",
            profile_id="python-cli",
            factory_version="0.14.5",
        )
        self.assertEqual(set(targets), set(OVERLAY_MANAGED_PATHS))
        for relative in targets:
            self.assertFalse(destination_is_forbidden(relative), relative)
            self.assertFalse(relative.startswith("src/"))
            self.assertFalse(relative.startswith("tests/"))
        skill = targets[SKILL_RELATIVE].decode("utf-8")
        self.assertIn("0.14.5", skill)
        self.assertIn("python-cli", skill)
        self.assertIn("demo", skill)
        answers = targets[ANSWERS_RELATIVE].decode("utf-8")
        self.assertIn("project-factory://overlay", answers)
        self.assertNotIn("D:\\", answers)
        self.assertNotIn("/Users/", answers)

    def test_refresh_updates_overlay_and_preserves_user_source(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "demo"
            source = root / "src" / "demo" / "app.py"
            tests = root / "tests" / "test_app.py"
            pyproject = root / "pyproject.toml"
            source.parent.mkdir(parents=True)
            tests.parent.mkdir(parents=True)
            user_source = b"USER_SOURCE_KEEP\n"
            user_tests = b"USER_TEST_KEEP\n"
            user_pyproject = b"[project]\nname='demo'\n"
            source.write_bytes(user_source)
            tests.write_bytes(user_tests)
            pyproject.write_bytes(user_pyproject)
            apply_factory_overlay(
                root,
                project_name="demo",
                profile_id="python-cli",
                factory_version="0.14.4",
            )
            first = (root / SKILL_RELATIVE).read_bytes()
            self.assertIn(b"0.14.4", first)
            apply_factory_overlay(
                root,
                project_name="demo",
                profile_id="python-cli",
                factory_version="0.14.5",
            )
            second = (root / SKILL_RELATIVE).read_bytes()
            self.assertIn(b"0.14.5", second)
            self.assertNotEqual(first, second)
            self.assertEqual(user_source, source.read_bytes())
            self.assertEqual(user_tests, tests.read_bytes())
            self.assertEqual(user_pyproject, pyproject.read_bytes())
            self.assertTrue((root / SPINE_RELATIVE).is_file())
            self.assertTrue((root / ANSWERS_RELATIVE).is_file())

    def test_generate_then_user_edit_survives_upgrade_plan_current(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            result = generate_project("做一个 Python 命令行工具。", "overlay-cli", Path(td))
            root = result.project_root
            candidates = [p for p in (root / "src").rglob("*.py") if p.is_file()]
            self.assertTrue(candidates)
            source = candidates[0]
            source.write_bytes(source.read_bytes() + b"\n# user domain change\n")
            source_after = source.read_bytes()
            skill_before = (root / SKILL_RELATIVE).read_bytes()
            plan = plan_upgrade(root)
            self.assertEqual(plan.status, "CURRENT")
            self.assertEqual(source_after, source.read_bytes())
            self.assertEqual(skill_before, (root / SKILL_RELATIVE).read_bytes())
            lock = json.loads((root / "project.lock.json").read_text(encoding="utf-8"))
            self.assertEqual(lock["factory"]["version"], FACTORY_VERSION)
            for relative in OVERLAY_MANAGED_PATHS:
                self.assertIn(relative, lock["managed_files"])

    def test_legacy_p7_upgrade_adds_overlay_without_touching_src(self) -> None:
        import zipfile

        golden = ROOT / "history" / "p7_golden_outputs" / "json-batch-cli.zip"
        with tempfile.TemporaryDirectory() as td:
            with zipfile.ZipFile(golden) as zf:
                zf.extractall(td)
            root = Path(td) / "json-batch-cli"
            source = root / "src/json_batch_cli/__init__.py"
            source.write_bytes(source.read_bytes() + b"\n# preserved user code\n")
            before = source.read_bytes()
            self.assertFalse((root / SKILL_RELATIVE).exists())
            plan = plan_upgrade(root)
            self.assertEqual(plan.status, "READY")
            paths = {c.path for c in plan.changes}
            self.assertIn(SKILL_RELATIVE, paths)
            self.assertNotIn("src/json_batch_cli/__init__.py", paths)
            applied = apply_upgrade(root, confirm_plan_sha256=plan.plan_sha256)
            self.assertEqual(applied["status"], "APPLIED")
            self.assertEqual(before, source.read_bytes())
            skill = (root / SKILL_RELATIVE).read_text(encoding="utf-8")
            self.assertIn(FACTORY_VERSION, skill)
            self.assertIn("json-batch-cli", skill)

    def test_unknown_template_variable_fails(self) -> None:
        with self.assertRaises(OverlayError):
            from project_factory import overlay as overlay_mod

            overlay_mod._render_text("hello {{ missing }}", {"project_name": "x"})


if __name__ == "__main__":
    unittest.main()
