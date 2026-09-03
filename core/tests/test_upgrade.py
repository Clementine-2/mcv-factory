from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from project_factory.factory import FACTORY_STAGE, FACTORY_VERSION, generate_project
from project_factory.ownership import verify_factory_overlay_manifest
from project_factory.upgrade import UpgradeError, apply_upgrade, plan_upgrade, rollback_upgrade


P7_GOLDEN = ROOT / "history" / "p7_golden_outputs" / "json-batch-cli.zip"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_p7(temp: Path) -> Path:
    with zipfile.ZipFile(P7_GOLDEN) as z:
        z.extractall(temp)
    return temp / "json-batch-cli"


def tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file() and not any(part in {".venv", "dist", "node_modules", "__pycache__", ".pytest_cache"} for part in p.relative_to(root).parts)
    }


class P8UpgradeTests(unittest.TestCase):
    def test_dry_run_p7_project_is_read_only_and_ready(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = extract_p7(Path(td))
            before = tree_bytes(root)
            plan = plan_upgrade(root)
            after = tree_bytes(root)
            self.assertEqual(before, after)
            self.assertEqual(plan.status, "READY")
            self.assertEqual(plan.risk, "MEDIUM")
            self.assertEqual(plan.source_lock_schema, "0.5")
            self.assertEqual(plan.target_lock_schema, "0.9")
            self.assertTrue(plan.plan_sha256)
            paths = {c.path for c in plan.changes}
            self.assertIn(".project/contract/agent-contract.md", paths)
            self.assertIn("AGENTS.md", paths)
            self.assertIn("CLAUDE.md", paths)
            self.assertNotIn("src/json_batch_cli/__init__.py", paths)
            contract_change = next(c for c in plan.changes if c.path == ".project/contract/agent-contract.md")
            self.assertIn("Factory upgrade discipline", contract_change.diff_preview or "")

    def test_business_source_change_does_not_block_overlay_upgrade(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = extract_p7(Path(td))
            source = root / "src/json_batch_cli/__init__.py"
            source.write_text(source.read_text(encoding="utf-8") + "\n# user domain change\n", encoding="utf-8")
            plan = plan_upgrade(root)
            self.assertEqual(plan.status, "READY")
            self.assertFalse(any(c.path.startswith("src/") for c in plan.changes))

    def test_modified_factory_owned_contract_blocks_upgrade(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = extract_p7(Path(td))
            path = root / "AGENTS.md"
            path.write_text(path.read_text(encoding="utf-8") + "\nUSER EDIT\n", encoding="utf-8")
            plan = plan_upgrade(root)
            self.assertEqual(plan.status, "BLOCKED")
            self.assertTrue(any("AGENTS.md" in item for item in plan.blocked_reasons))

    def test_blueprint_provenance_change_blocks_upgrade(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = extract_p7(Path(td))
            path = root / ".project/blueprint.yaml"
            path.write_text(path.read_text(encoding="utf-8") + "\n# edited\n", encoding="utf-8")
            # comment-only YAML does not alter parsed semantics; make a semantic change too.
            text = path.read_text(encoding="utf-8").replace("批量读取一个目录里的 JSON 并转换格式", "批量读取一个目录里的 JSON 并转换成另一种格式")
            path.write_text(text, encoding="utf-8")
            plan = plan_upgrade(root)
            self.assertEqual(plan.status, "BLOCKED")
            self.assertTrue(any("Blueprint" in item for item in plan.blocked_reasons))

    def test_apply_requires_exact_dry_run_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = extract_p7(Path(td))
            before = tree_bytes(root)
            with self.assertRaisesRegex(UpgradeError, "confirmation hash"):
                apply_upgrade(root, confirm_plan_sha256="not-the-plan")
            self.assertEqual(before, tree_bytes(root))
            self.assertFalse((root.parent / ".project-factory-rollback").exists())

    def test_stale_plan_is_detected_by_confirmation_hash(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = extract_p7(Path(td))
            plan = plan_upgrade(root)
            path = root / ".project/generation.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["external_note"] = "changed after dryrun"
            path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            with self.assertRaises(UpgradeError):
                apply_upgrade(root, confirm_plan_sha256=plan.plan_sha256)

    def test_apply_creates_rollback_point_updates_only_overlay_and_verifies(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = extract_p7(Path(td))
            source = root / "src/json_batch_cli/__init__.py"
            source.write_text(source.read_text(encoding="utf-8") + "\n# preserved user code\n", encoding="utf-8")
            source_before = source.read_bytes()
            generation_manifest_before = (root / "PROJECT_MANIFEST.sha256").read_bytes()
            plan = plan_upgrade(root)
            result = apply_upgrade(root, confirm_plan_sha256=plan.plan_sha256)
            self.assertEqual(result["status"], "APPLIED")
            self.assertEqual(source_before, source.read_bytes())
            rollback = Path(result["rollback_bundle"])
            self.assertTrue(rollback.is_file())
            self.assertEqual(sha256(rollback), result["rollback_bundle_sha256"])
            lock = json.loads((root / "project.lock.json").read_text(encoding="utf-8"))
            self.assertEqual(lock["lock_schema_version"], "0.9")
            self.assertEqual(lock["factory"]["version"], FACTORY_VERSION)
            self.assertEqual(lock["factory"]["stage"], FACTORY_STAGE)
            self.assertTrue(lock["upgrade_history"])
            self.assertTrue(lock["managed_files"])
            self.assertFalse(lock["upgrade_contract"]["automatic_apply"])
            contract = (root / ".project/contract/agent-contract.md").read_bytes()
            self.assertEqual(contract, (root / "AGENTS.md").read_bytes())
            self.assertEqual(contract, (root / "CLAUDE.md").read_bytes())
            evidence = json.loads((root / ".project/evidence/upgrade-verification.json").read_text(encoding="utf-8"))
            self.assertEqual(evidence["status"], "VERIFIED")
            self.assertFalse(evidence["rollback_bundle"]["independent_disaster_backup"])
            self.assertEqual(generation_manifest_before, (root / "PROJECT_MANIFEST.sha256").read_bytes())
            ok, failures = verify_factory_overlay_manifest(root)
            self.assertTrue(ok, failures)
            self.assertTrue((root / "skills/factory-discipline/SKILL.md").is_file())
            self.assertTrue((root / ".project/overlay/VERIFICATION_SPINE.md").is_file())
            self.assertTrue((root / ".copier-answers.factory-overlay.yml").is_file())
            self.assertEqual(source_before, source.read_bytes())

    def test_rollback_restores_exact_preupgrade_project_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = extract_p7(Path(td))
            source = root / "src/json_batch_cli/__init__.py"
            source.write_text(source.read_text(encoding="utf-8") + "\n# pre-upgrade user code\n", encoding="utf-8")
            before = tree_bytes(root)
            plan = plan_upgrade(root)
            applied = apply_upgrade(root, confirm_plan_sha256=plan.plan_sha256)
            bundle = Path(applied["rollback_bundle"])
            with self.assertRaisesRegex(UpgradeError, "confirmation hash"):
                rollback_upgrade(root, bundle, confirm_bundle_sha256="wrong")
            rolled = rollback_upgrade(root, bundle, confirm_bundle_sha256=applied["rollback_bundle_sha256"])
            self.assertEqual(rolled["status"], "ROLLED_BACK")
            self.assertEqual(before, tree_bytes(root))

    def test_rollback_refuses_to_overwrite_post_upgrade_edits(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = extract_p7(Path(td))
            plan = plan_upgrade(root)
            applied = apply_upgrade(root, confirm_plan_sha256=plan.plan_sha256)
            bundle = Path(applied["rollback_bundle"])
            agents = root / "AGENTS.md"
            agents.write_text(agents.read_text(encoding="utf-8") + "\nPOST-UPGRADE USER EDIT\n", encoding="utf-8")
            with self.assertRaisesRegex(UpgradeError, "overwrite post-upgrade changes"):
                rollback_upgrade(root, bundle, confirm_bundle_sha256=applied["rollback_bundle_sha256"])

    def test_current_p8_project_with_missing_overlay_manifest_is_not_called_current(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            result = generate_project("做一个 Python 命令行工具。", "p8-current-check", Path(td))
            (result.project_root / ".project/FACTORY_OVERLAY_MANIFEST.sha256").unlink()
            plan = plan_upgrade(result.project_root)
            self.assertEqual(plan.status, "BLOCKED")
            self.assertTrue(any("Factory Overlay Manifest" in item for item in plan.blocked_reasons))

    def test_new_p8_project_is_upgrade_ready_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            result = generate_project("做一个 Python 命令行工具。", "p8-cli", out)
            lock = json.loads((result.project_root / "project.lock.json").read_text(encoding="utf-8"))
            self.assertEqual(lock["lock_schema_version"], "0.9")
            self.assertTrue(lock["managed_files"])
            before = tree_bytes(result.project_root)
            plan = plan_upgrade(result.project_root)
            self.assertEqual(plan.status, "CURRENT")
            self.assertEqual(before, tree_bytes(result.project_root))
            # A current P9 project must be a true no-op.
            self.assertEqual(plan.changes, ())
            self.assertTrue((result.project_root / "skills/factory-discipline/SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
