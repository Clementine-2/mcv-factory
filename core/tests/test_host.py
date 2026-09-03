from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from project_factory.factory import generate_project, restore_verify_project_zip
from project_factory.host import (
    HOST_EVIDENCE_PATH,
    HOST_README_PATH,
    HostError,
    HostSpec,
    build_host_plan,
    load_host_registry,
    materialize_host_plans,
    verify_host_materialization,
)

REQ = "做一个 Python CLI 工具，不能覆盖原始文件。"


class HostRegistryTests(unittest.TestCase):
    def test_aionui_contract_is_acp_and_non_owning(self) -> None:
        registry = load_host_registry()
        spec = registry["aionui"]
        self.assertEqual(spec.protocol, "acp")
        self.assertEqual(set(spec.target_harnesses), {"codex", "claude"})
        self.assertFalse(spec.default)
        self.assertTrue(all(value is False for value in spec.boundaries.values()))

    def test_plan_requires_compatible_materialized_harness(self) -> None:
        spec = load_host_registry()["aionui"]
        with self.assertRaisesRegex(HostError, "no compatible"):
            build_host_plan(spec, {"other": {"context_file": "OTHER.md"}})

    def test_host_with_ownership_claim_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "hosts.yaml"
            path.write_text(
                '''schema_version: "0.1"\nhosts:\n  - id: bad\n    adapter_version: "0.1"\n    kind: gui\n    protocol: acp\n    target_harnesses: [codex]\n    boundaries:\n      owns_extensions: true\n      owns_verification: false\n      owns_runner: false\n      owns_harness_runtime: false\n      owns_project_lock: false\n''',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(HostError, "non-ownership"):
                load_host_registry(path)


class HostMaterializationTests(unittest.TestCase):
    def _adapters(self) -> dict[str, dict[str, str]]:
        return {
            "codex": {"context_file": "AGENTS.md"},
            "claude": {"context_file": "CLAUDE.md"},
        }

    def test_materialization_is_plan_only_and_runtime_unverified(self) -> None:
        spec = load_host_registry()["aionui"]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report = materialize_host_plans(root, (spec,), self._adapters())
            self.assertEqual(report["status"], "PARTIALLY_VERIFIED")
            self.assertFalse(report["hosts"]["aionui"]["runtime_verified"])
            plan = json.loads((root / ".project/host/aionui.json").read_text(encoding="utf-8"))
            self.assertEqual(plan["mode"], "plan-only")
            self.assertFalse(plan["runtime"]["host_process_started"])
            self.assertFalse(plan["runtime"]["live_task_executed"])
            self.assertFalse((root / ".aionui").exists())
            self.assertTrue((root / HOST_EVIDENCE_PATH).is_file())
            self.assertTrue((root / HOST_README_PATH).is_file())
            locked = {"hosts": report["hosts"]}
            checked = verify_host_materialization(root, locked)
            self.assertEqual(checked["status"], "PARTIALLY_VERIFIED")

    def test_tampered_host_plan_fails_verification(self) -> None:
        spec = load_host_registry()["aionui"]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report = materialize_host_plans(root, (spec,), self._adapters())
            path = root / ".project/host/aionui.json"
            path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            checked = verify_host_materialization(root, {"hosts": report["hosts"]})
            self.assertEqual(checked["status"], "FAILED")
            self.assertTrue(any("hash mismatch" in item for item in checked["failures"]))


class HostFactoryIntegrationTests(unittest.TestCase):
    def test_host_is_opt_in_no_default_framework_tax(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            result = generate_project(REQ, "no-host-cli", Path(td))
            self.assertIsNone(result.host_integration)
            self.assertFalse((result.project_root / ".project/host").exists())
            lock = json.loads((result.project_root / "project.lock.json").read_text(encoding="utf-8"))
            self.assertIsNone(lock["host_integration"])

    def test_aionui_host_plan_survives_project_zip_restore(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            result = generate_project(REQ, "hosted-cli", Path(td), hosts=("aionui",))
            self.assertEqual(result.host_integration["status"], "PARTIALLY_VERIFIED")
            lock = json.loads((result.project_root / "project.lock.json").read_text(encoding="utf-8"))
            self.assertEqual(lock["lock_schema_version"], "0.9")
            self.assertEqual(set(lock["host_integration"]["hosts"]), {"aionui"})
            self.assertFalse(lock["host_integration"]["runtime_verified"])
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["host_integration"]["status"], "PARTIALLY_VERIFIED")
            self.assertFalse(restored["host_integration"]["runtime_verified"])


if __name__ == "__main__":
    unittest.main()

class HostUpgradeBoundaryTests(unittest.TestCase):
    def test_tampered_factory_owned_host_plan_blocks_current_upgrade_analysis(self) -> None:
        from project_factory.upgrade import plan_upgrade
        with tempfile.TemporaryDirectory() as td:
            result = generate_project(REQ, "host-upgrade-cli", Path(td), hosts=("aionui",))
            plan_path = result.project_root / ".project/host/aionui.json"
            plan_path.write_text(plan_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            plan = plan_upgrade(result.project_root)
            self.assertEqual(plan.status, "BLOCKED")
            self.assertTrue(any("host/aionui.json" in item for item in plan.blocked_reasons))
