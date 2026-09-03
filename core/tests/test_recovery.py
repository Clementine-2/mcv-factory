from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from project_factory.recovery import (  # noqa: E402
    RecoveryError,
    apply_checkpoint_restore,
    inspect_checkpoint,
    plan_checkpoint_restore,
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_checkpoint(root: Path, *, tamper: bool = False, unsafe: bool = False) -> Path:
    archive = root / "checkpoint.zip"
    payload = b"hello checkpoint\n"
    digest = sha256_bytes(payload)
    manifest = f"{digest}  data.txt\n".encode()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("factory-root/data.txt", b"tampered\n" if tamper else payload)
        zf.writestr("factory-root/MANIFEST.sha256", manifest)
        zf.writestr("factory-root/CHECKPOINT_P9_COMPLETE.md", "old\n")
        zf.writestr("factory-root/CHECKPOINT_P12_COMPLETE.md", "current\n")
        if unsafe:
            zf.writestr("../escape.txt", "no\n")
    return archive


class CheckpointRecoveryTests(unittest.TestCase):
    def test_inspect_verifies_crc_manifest_and_latest_stage_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            archive = make_checkpoint(Path(td))
            result = inspect_checkpoint(archive)
        self.assertEqual(result["status"], "VERIFIED")
        self.assertEqual(result["manifest_entries"], 1)
        self.assertTrue(result["checkpoint_metadata_file"].endswith("CHECKPOINT_P12_COMPLETE.md"))

    def test_pinf_checkpoint_metadata_supersedes_numbered_core_stage(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            archive = make_checkpoint(base)
            rewritten = base / "checkpoint-pinf.zip"
            with zipfile.ZipFile(archive, "r") as source, zipfile.ZipFile(rewritten, "w", zipfile.ZIP_DEFLATED) as target:
                for info in source.infolist():
                    target.writestr(info, source.read(info.filename))
                target.writestr("factory-root/CHECKPOINT_PINF_UX1_COMPLETE.md", "continuous evolution\n")
            result = inspect_checkpoint(rewritten)
        self.assertEqual(result["status"], "VERIFIED")
        self.assertTrue(result["checkpoint_metadata_file"].endswith("CHECKPOINT_PINF_UX1_COMPLETE.md"))

    def test_expected_outer_sha_mismatch_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            archive = make_checkpoint(Path(td))
            with self.assertRaisesRegex(RecoveryError, "does not match"):
                inspect_checkpoint(archive, expected_zip_sha256="0" * 64)

    def test_manifest_tamper_is_reported_not_hidden(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            archive = make_checkpoint(Path(td), tamper=True)
            result = inspect_checkpoint(archive)
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["manifest_failures"], ["sha256:data.txt"])

    def test_unsafe_zip_member_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            archive = make_checkpoint(Path(td), unsafe=True)
            with self.assertRaisesRegex(RecoveryError, "Unsafe checkpoint ZIP member"):
                inspect_checkpoint(archive)

    def test_plan_is_read_only_and_refuses_existing_destination(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            archive = make_checkpoint(base)
            destination = base / "restore-new"
            plan = plan_checkpoint_restore(archive, destination)
            self.assertEqual(plan.status, "READY")
            self.assertFalse(destination.exists())
            destination.mkdir()
            with self.assertRaisesRegex(RecoveryError, "already exists"):
                plan_checkpoint_restore(archive, destination)

    def test_wrong_plan_hash_blocks_before_destination_creation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            archive = make_checkpoint(base)
            destination = base / "restore-new"
            with self.assertRaisesRegex(RecoveryError, "confirmation hash"):
                apply_checkpoint_restore(
                    archive,
                    destination,
                    confirm_plan_sha256="0" * 64,
                )
            self.assertFalse(destination.exists())

    def test_exact_plan_restores_to_new_directory_and_verifies_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            archive = make_checkpoint(base)
            destination = base / "restore-new"
            plan = plan_checkpoint_restore(archive, destination)
            result = apply_checkpoint_restore(
                archive,
                destination,
                confirm_plan_sha256=plan.plan_sha256,
            )
            self.assertEqual(result["status"], "RESTORED")
            self.assertEqual(result["manifest"]["status"], "PASS")
            self.assertEqual((destination / "factory-root/data.txt").read_text(), "hello checkpoint\n")
            self.assertFalse(result["overwrite_performed"])
            self.assertFalse(result["automatic_delete_on_failure"])

    def test_checkpoint_cli_plan_is_json_and_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            archive = make_checkpoint(base)
            destination = base / "cli-restore"
            env = dict(os.environ)
            env["PYTHONPATH"] = str(ROOT / "src")
            import subprocess
            result = subprocess.run(
                [sys.executable, "-m", "project_factory", "checkpoint", "plan", str(archive), "--out-dir", str(destination)],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "READY")
            self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
