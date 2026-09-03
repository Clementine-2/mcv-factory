from __future__ import annotations

import json
import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from project_factory.process import (
    ProcessIntegrationError,
    build_process_plan,
    execute_process_plan,
    load_process_registry,
    materialize_process_plan,
    resolve_process_integration,
    verify_process_materialization,
)


def _write_fake_specify(directory: Path) -> Path:
    body = textwrap.dedent(
        """\
        import json
        import sys
        from pathlib import Path

        args = sys.argv[1:]
        root = Path.cwd()
        if args == ["version"]:
            print("Specify CLI 1.0.1")
            raise SystemExit(0)

        state_path = root / ".specify" / "integration.json"
        def load_state():
            if state_path.exists():
                return json.loads(state_path.read_text(encoding="utf-8"))
            return {"default_integration": None, "installed_integrations": []}
        def save_state(state):
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(json.dumps(state), encoding="utf-8")
        def install_skill(key):
            target = {
                "codex": root / ".agents" / "skills" / "speckit-specify" / "SKILL.md",
                "claude": root / ".claude" / "skills" / "speckit-specify" / "SKILL.md",
            }[key]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("---\\nname: speckit-specify\\n---\\n", encoding="utf-8")

        if len(args) >= 4 and args[0] == "init" and args[1] == "--here" and "--integration" in args:
            key = args[args.index("--integration") + 1]
            state = load_state()
            state["default_integration"] = key
            if key not in state["installed_integrations"]:
                state["installed_integrations"].append(key)
            save_state(state)
            install_skill(key)
            print(f"initialized {key}")
            raise SystemExit(0)

        if len(args) >= 3 and args[:2] == ["integration", "install"]:
            key = args[2]
            state = load_state()
            if state.get("default_integration") is None:
                state["default_integration"] = key
            if key not in state["installed_integrations"]:
                state["installed_integrations"].append(key)
            save_state(state)
            install_skill(key)
            print(f"installed {key}")
            raise SystemExit(0)

        if args == ["integration", "status"]:
            state = load_state()
            print(json.dumps(state))
            raise SystemExit(0)

        print("unsupported", args, file=sys.stderr)
        raise SystemExit(9)
        """
    )
    py_path = directory / "specify.py"
    py_path.write_text(body, encoding="utf-8")
    if os.name == "nt":
        cmd = directory / "specify.cmd"
        cmd.write_text(f'@echo off\r\n"{sys.executable}" "%~dp0specify.py" %*\r\n', encoding="utf-8")
        return cmd
    unix = directory / "specify"
    unix.write_text("#!/usr/bin/env python3\n" + body, encoding="utf-8")
    unix.chmod(0o755)
    return unix


class ProcessPlanTests(unittest.TestCase):
    def test_pinned_spec_kit_contract_is_plan_only_by_default(self) -> None:
        spec = resolve_process_integration("spec-kit")
        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertEqual(spec.upstream_version, "1.0.1")
        self.assertFalse(spec.runtime_verified)
        self.assertFalse(spec.agent_context_extension)
        self.assertIn("test double", spec.notes.lower())
        plan = build_process_plan(spec, ("codex", "claude"))
        self.assertEqual(plan["commands"][0], ["specify", "init", "--here", "--integration", "codex", "--script", "py"])
        self.assertIn(["specify", "integration", "install", "claude", "--script", "py"], plan["commands"])
        self.assertEqual(plan["commands"][-1], ["specify", "integration", "status"])
        self.assertFalse(plan["agent_context_extension"])

    def test_plan_materialization_does_not_fake_installation(self) -> None:
        spec = resolve_process_integration("spec-kit")
        assert spec is not None
        plan = build_process_plan(spec, ("codex", "claude"))
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            report = materialize_process_plan(root, plan)
            self.assertEqual(report["status"], "PLANNED_NOT_INSTALLED")
            self.assertFalse(report["runtime_verified"])
            self.assertFalse((root / ".specify").exists())
            lock = {
                "provider": report["provider"],
                "status": report["status"],
                "runtime_verified": False,
                "target_harnesses": list(plan["target_harnesses"]),
            }
            checked = verify_process_materialization(root, lock)
            self.assertEqual(checked["status"], "PLANNED_NOT_INSTALLED")
            self.assertFalse(checked["runtime_verified"])

    def test_execute_mode_fails_closed_when_specify_is_unavailable(self) -> None:
        spec = resolve_process_integration("spec-kit")
        assert spec is not None
        plan = build_process_plan(spec, ("codex",))
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            materialize_process_plan(root, plan)
            with self.assertRaisesRegex(ProcessIntegrationError, "not available"):
                execute_process_plan(root, spec, plan, env={"PATH": ""})

    def test_trusted_adapter_command_flow_with_contract_test_double(self) -> None:
        spec = resolve_process_integration("spec-kit")
        assert spec is not None
        plan = build_process_plan(spec, ("codex", "claude"))
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            _write_fake_specify(bin_dir)
            project = root / "project"
            project.mkdir()
            materialize_process_plan(project, plan)
            env = dict(os.environ)
            env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
            report = execute_process_plan(project, spec, plan, env=env)
            self.assertEqual(report["status"], "INSTALLED_CONTRACT_VERIFIED")
            self.assertTrue(report["runtime_verified"])
            state = json.loads((project / ".specify/integration.json").read_text(encoding="utf-8"))
            self.assertEqual(state["default_integration"], "codex")
            self.assertEqual(set(state["installed_integrations"]), {"codex", "claude"})
            self.assertTrue((project / ".agents/skills/speckit-specify/SKILL.md").is_file())
            self.assertTrue((project / ".claude/skills/speckit-specify/SKILL.md").is_file())
            # Evidence must not leak the temporary executable path.
            serialized = json.dumps(report, ensure_ascii=False)
            self.assertNotIn(str(bin_dir), serialized)

    def test_unknown_process_integration_is_rejected(self) -> None:
        with self.assertRaisesRegex(ProcessIntegrationError, "Unknown process integration"):
            resolve_process_integration("not-real")


if __name__ == "__main__":
    unittest.main()
