from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from project_factory.factory import (  # noqa: E402
    MAX_PROJECT_NAME_CHARS,
    FactoryError,
    _safe_project_name,
    _zip_directory,
    restore_verify_project_zip,
    verify_project_manifest,
)
from project_factory.normalizer import MAX_REQUIREMENT_CHARS, normalize_requirement  # noqa: E402
from project_factory.recipes import RecipeError, run_command  # noqa: E402
from project_factory.recovery import RecoveryError, inspect_checkpoint  # noqa: E402
from project_factory.registry import RegistryError, inspect_provider, load_registry  # noqa: E402
from project_factory.ux import check_project, main as ux_main  # noqa: E402
from project_factory.verification import _execute_command  # noqa: E402


class HumanUXTests(unittest.TestCase):
    def test_empty_command_is_help_not_blueprint_error(self) -> None:
        stream = io.StringIO()
        with redirect_stdout(stream):
            rc = ux_main([])
        self.assertEqual(rc, 0)
        text = stream.getvalue()
        self.assertIn("status -> new -> check -> verify", text)
        self.assertIn("new", text)
        self.assertNotIn("blueprint", text.casefold().splitlines()[0])

    def test_root_module_help_uses_human_surface(self) -> None:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT / "src")
        result = subprocess.run(
            [sys.executable, "-m", "project_factory", "--help"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("status -> new -> check -> verify", result.stdout)
        self.assertIn("Advanced commands", result.stdout)

    def test_check_known_golden_project_is_read_only_pass(self) -> None:
        root = ROOT / "golden_outputs" / "json-batch-cli"
        before = (root / "project.lock.json").read_bytes()
        result = check_project(root)
        after = (root / "project.lock.json").read_bytes()
        self.assertEqual(result["status"], "PASS", result["failures"])
        self.assertFalse(result["runtime_execution_performed"])
        self.assertEqual(before, after)

    def test_check_zip_gives_specific_verify_guidance(self) -> None:
        stream = io.StringIO()
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "project.zip"
            path.write_bytes(b"not-a-real-zip")
            with redirect_stdout(stream):
                rc = ux_main(["check", str(path)])
        self.assertEqual(rc, 4)
        self.assertIn("use 'project-factory verify", stream.getvalue())


class SafetyHardeningTests(unittest.TestCase):
    def test_requirement_size_is_bounded_before_normalization(self) -> None:
        with self.assertRaisesRegex(ValueError, "too large"):
            normalize_requirement("x" * (MAX_REQUIREMENT_CHARS + 1))

    def test_project_name_size_is_bounded(self) -> None:
        with self.assertRaisesRegex(FactoryError, "1-128"):
            _safe_project_name("x" * (MAX_PROJECT_NAME_CHARS + 1))

    def test_project_manifest_rejects_parent_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "project"
            root.mkdir()
            outside = Path(td) / "outside.txt"
            outside.write_text("outside", encoding="utf-8")
            digest = hashlib.sha256(outside.read_bytes()).hexdigest()
            (root / "PROJECT_MANIFEST.sha256").write_text(
                f"{digest}  ../outside.txt\n", encoding="utf-8"
            )
            ok, failures = verify_project_manifest(root)
        self.assertFalse(ok)
        self.assertEqual(failures, ["Unsafe manifest path: ../outside.txt"])

    def test_project_restore_rejects_zip_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            archive = Path(td) / "evil.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("../escape.txt", "no")
            with self.assertRaisesRegex(FactoryError, "Unsafe project ZIP member"):
                restore_verify_project_zip(archive)
            self.assertFalse((Path(td).parent / "escape.txt").exists())

    def test_project_restore_rejects_backslash_member(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            archive = Path(td) / "evil.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("root\\..\\escape.txt", "no")
            with self.assertRaisesRegex(FactoryError, "Unsafe project ZIP member"):
                restore_verify_project_zip(archive)

    def test_checkpoint_inspection_rejects_backslash_member(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            archive = Path(td) / "evil.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("root\\..\\escape.txt", "no")
            with self.assertRaisesRegex(RecoveryError, "Unsafe checkpoint ZIP member"):
                inspect_checkpoint(archive)

    def test_project_zip_writer_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            project = base / "demo"
            project.mkdir()
            (project / "a.txt").write_text("a", encoding="utf-8")
            archive = base / "demo.zip"
            _zip_directory(project, archive)
            original = archive.read_bytes()
            with self.assertRaises(FileExistsError):
                _zip_directory(project, archive)
            self.assertEqual(archive.read_bytes(), original)


class TimeoutBoundaryTests(unittest.TestCase):
    def test_recipe_timeout_is_visible_failure(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            with mock.patch(
                "project_factory.recipes.subprocess.run",
                side_effect=subprocess.TimeoutExpired(["tool"], 180, output="partial"),
            ):
                with self.assertRaisesRegex(RecipeError, "timed out"):
                    run_command(["tool"], Path(td))

    def test_provider_probe_timeout_is_visible_failure(self) -> None:
        spec = load_registry().providers["uv"]
        with mock.patch("project_factory.registry.shutil.which", return_value="/fake/uv"):
            with mock.patch(
                "project_factory.registry.subprocess.run",
                side_effect=subprocess.TimeoutExpired(["uv", "--version"], 15),
            ):
                with self.assertRaisesRegex(RegistryError, "timed out"):
                    inspect_provider(spec)

    def test_verification_timeout_becomes_failed_command_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            with mock.patch(
                "project_factory.verification.subprocess.run",
                side_effect=subprocess.TimeoutExpired(["tool"], 180, output="partial", stderr="err"),
            ):
                result = _execute_command(("tool",), Path(td))
        self.assertEqual(result["returncode"], 124)
        self.assertTrue(result["timed_out"])
        self.assertIn("timed out", result["stderr"])


if __name__ == "__main__":
    unittest.main()
