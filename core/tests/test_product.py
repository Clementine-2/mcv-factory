from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from project_factory.factory import FACTORY_STAGE, FACTORY_VERSION  # noqa: E402
from project_factory.product import bootstrap, doctor  # noqa: E402


class ProductDoctorTests(unittest.TestCase):
    def test_doctor_is_read_only_and_reports_ready_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            before = sorted(path.relative_to(work).as_posix() for path in work.rglob("*"))
            old = Path.cwd()
            try:
                os.chdir(work)
                result = doctor(deep=False)
            finally:
                os.chdir(old)
            after = sorted(path.relative_to(work).as_posix() for path in work.rglob("*"))
        self.assertEqual(before, after)
        self.assertIn(result["status"], {"READY", "READY_WITH_WARNINGS"})
        self.assertEqual(result["factory"], {"version": FACTORY_VERSION, "stage": FACTORY_STAGE})
        self.assertTrue(result["ready_profiles"])
        self.assertEqual(result["deep_smoke"]["status"], "NOT_RUN")

    def test_deep_doctor_uses_temporary_project_and_restores_it(self) -> None:
        result = doctor(deep=True)
        self.assertIn(result["status"], {"READY", "READY_WITH_WARNINGS"})
        self.assertEqual(result["deep_smoke"]["status"], "PASS")
        self.assertEqual(result["deep_smoke"]["generation_status"], "VERIFIED")
        self.assertEqual(result["deep_smoke"]["restore_status"], "VERIFIED")
        self.assertFalse(result["deep_smoke"]["persistent_output"])

    def test_bootstrap_creates_no_persistent_factory_state(self) -> None:
        result = bootstrap(deep=False)
        self.assertEqual(result["status"], "READY")
        self.assertFalse(result["persistent_state_created"])
        self.assertIn("project-factory status", result["quickstart"]["status"])
        self.assertIn("project-factory new", result["quickstart"]["new"])
        self.assertIn("project-factory check", result["quickstart"]["check"])
        self.assertIn("project-factory verify", result["quickstart"]["verify"])
        self.assertIn("project-factory generate", result["quickstart"]["generate"])

    def test_module_version_entrypoint(self) -> None:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT / "src")
        result = subprocess.run(
            [sys.executable, "-m", "project_factory", "--version"],
            cwd=ROOT,
            env=env,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(FACTORY_VERSION, result.stdout)
        self.assertIn(FACTORY_STAGE, result.stdout)

    def test_doctor_cli_emits_machine_readable_json(self) -> None:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT / "src")
        result = subprocess.run(
            [sys.executable, "-m", "project_factory", "doctor"],
            cwd=ROOT,
            env=env,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertIn(payload["status"], {"READY", "READY_WITH_WARNINGS"})
        self.assertEqual(payload["factory"]["version"], FACTORY_VERSION)


if __name__ == "__main__":
    unittest.main()
