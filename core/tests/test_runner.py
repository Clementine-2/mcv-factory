from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import textwrap
import unittest
from contextlib import contextmanager
from pathlib import Path

import yaml

from project_factory.decision import IntentSnapshot
from project_factory.factory import FactoryError, generate_project, restore_verify_project_zip
from project_factory.runner import (
    RUNNER_ADMISSION_LOCK_PATH,
    RUNNER_CONTRACT_PATH,
    RUNNER_EVIDENCE_PATH,
    RUNNER_PLAN_PATH,
    RUNNER_README_PATH,
    RUNNER_STATE_README_PATH,
    RunnerConfig,
    RunnerError,
    _project_admission_lock,
    build_runner_plan,
    load_runner_registry,
    probe_runner_runtime,
    resolve_runner,
    runner_status,
    start_runner,
    stop_runner,
    validate_runner_runtime,
    verify_runner_materialization,
)

PYTHON_CLI_REQUIREMENT = "做一个 Python 命令行工具，批量读取一个目录里的 JSON 并转换格式。不能覆盖原始文件。"


def _write_fake_dagu(root: Path, *, fail_validate: bool = False, fail_dry: bool = False, fail_start: bool = False) -> tuple[dict[str, str], Path]:
    bin_dir = root / "fake-bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    log_path = root / "dagu-calls.log"
    py_path = bin_dir / "dagu.py"
    py_path.write_text(
        textwrap.dedent(
            f"""\
            import os
            import sys

            args = sys.argv[1:]
            log_path = os.environ["DAGU_FAKE_LOG"]
            with open(log_path, "a", encoding="utf-8") as handle:
                handle.write(" ".join(args) + "\\n")
            command = args[0] if args else ""
            if command == "version":
                print("dagu version 2.11.2")
                raise SystemExit(0)
            if command == "validate":
                raise SystemExit({1 if fail_validate else 0})
            if command == "dry":
                raise SystemExit({1 if fail_dry else 0})
            if command == "start":
                raise SystemExit({9 if fail_start else 0})
            if command == "status":
                print('{{"status":"running"}}')
                raise SystemExit(0)
            if command == "stop":
                print('{{"status":"stopped"}}')
                raise SystemExit(0)
            raise SystemExit(64)
            """
        ),
        encoding="utf-8",
    )
    if os.name == "nt":
        (bin_dir / "dagu.cmd").write_text(
            f'@echo off\r\n"{sys.executable}" "%~dp0dagu.py" %*\r\n',
            encoding="utf-8",
        )
    else:
        unix = bin_dir / "dagu"
        unix.write_text(
            "#!/bin/sh\nset -eu\n"
            + f'export DAGU_FAKE_LOG="${{DAGU_FAKE_LOG}}"\n'
            + f'exec "{sys.executable}" "{py_path.as_posix()}" "$@"\n',
            encoding="utf-8",
        )
        unix.chmod(unix.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([str(bin_dir), env.get("PATH", "")])
    env["DAGU_FAKE_LOG"] = str(log_path)
    return env, log_path


class RunnerRegistryTests(unittest.TestCase):
    def test_dagu_registry_contract_is_bounded_and_tag_locked(self) -> None:
        registry = load_runner_registry()
        spec = registry["dagu"]
        self.assertTrue(spec.default)
        self.assertEqual(spec.capability, "long_running_execution")
        self.assertEqual(spec.protocol, "dagu-yaml-v2")
        self.assertEqual(set(spec.allowed_harnesses), {"codex", "claude"})
        self.assertEqual(spec.upstream_contract["release_observed"], "2.11.2")
        self.assertEqual(
            spec.upstream_contract["tag_commit"],
            "a1a3c286b26cbad934bb9f8344f2f9aa51385981",
        )
        self.assertEqual(
            spec.upstream_contract["local_max_active_runs_semantics"],
            "deprecated_ignored_for_local_dag_queues",
        )
        self.assertTrue(spec.features["harness_run"])
        self.assertTrue(spec.features["repeat_policy"])
        self.assertTrue(spec.features["retry_policy"])
        self.assertTrue(spec.features["max_active_steps"])
        self.assertTrue(all(value is False for value in spec.boundaries.values()))

    def test_unknown_runner_fails_closed(self) -> None:
        with self.assertRaisesRegex(RunnerError, "Unknown Runner provider"):
            resolve_runner("not-real")


class RunnerPlanTests(unittest.TestCase):
    def test_plan_uses_v2112_canonical_schema_and_bounded_batch(self) -> None:
        spec = resolve_runner("dagu")
        config = RunnerConfig(
            wall_clock_timeout_sec=3600,
            batch_timeout_sec=600,
            max_batches=4,
            batch_interval_sec=7,
            retry_limit=2,
            retry_interval_sec=11,
            retry_max_interval_sec=60,
        )
        plan = build_runner_plan(
            spec,
            "runner-cli",
            harness_id="codex",
            verification_commands=[["uv", "--offline", "run", "python", "-m", "unittest", "discover", "-s", "tests", "-v"]],
            runtime_kind="python",
            scaffolder_executable="uv",
            config=config,
        )
        self.assertEqual(plan["type"], "chain")
        self.assertEqual(plan["working_dir"], "../..")
        self.assertEqual(plan["timeout_sec"], 3600)
        self.assertEqual(plan["max_active_steps"], 1)
        self.assertEqual(plan["max_active_runs"], 1)

        batch = plan["steps"][0]
        self.assertEqual(batch["action"], "harness.run")
        self.assertEqual(batch["with"]["provider"], "codex")
        self.assertEqual(batch["timeout_sec"], 600)
        self.assertEqual(batch["retry_policy"]["limit"], 2)
        self.assertEqual(batch["retry_policy"]["interval_sec"], 11)
        self.assertTrue(batch["retry_policy"]["backoff"])
        self.assertEqual(batch["retry_policy"]["max_interval_sec"], 60)
        self.assertEqual(batch["repeat_policy"]["repeat"], "until")
        self.assertEqual(batch["repeat_policy"]["limit"], 4)
        self.assertEqual(batch["repeat_policy"]["interval_sec"], 7)
        self.assertIn("CANDIDATE_DONE.flag", batch["repeat_policy"]["condition"])
        self.assertIn("Agent claim", batch["with"]["prompt"])
        self.assertNotIn("verified complete", batch["with"]["prompt"].casefold())

        gate = plan["steps"][1]
        self.assertEqual(gate["action"], "exec")
        self.assertNotIn("exec", gate)
        self.assertEqual(gate["with"]["command"], "uv")
        self.assertIsInstance(gate["with"]["args"], list)

    def test_runner_config_bounds_fail_closed(self) -> None:
        invalid = [
            RunnerConfig(wall_clock_timeout_sec=299),
            RunnerConfig(batch_timeout_sec=59),
            RunnerConfig(wall_clock_timeout_sec=600, batch_timeout_sec=601),
            RunnerConfig(max_batches=33),
            RunnerConfig(retry_limit=4),
            RunnerConfig(retry_interval_sec=100, retry_max_interval_sec=50),
        ]
        for config in invalid:
            with self.subTest(config=config):
                with self.assertRaises(RunnerError):
                    config.validate()

    def test_unsupported_harness_fails_closed(self) -> None:
        with self.assertRaisesRegex(RunnerError, "does not declare harness"):
            build_runner_plan(
                resolve_runner("dagu"),
                "bad-harness",
                harness_id="gemini",
                verification_commands=[["python", "-V"]],
                runtime_kind="python",
                scaffolder_executable="uv",
            )


class RunnerGenerationTests(unittest.TestCase):
    def test_default_interactive_project_has_no_runner_surface(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            result = generate_project(PYTHON_CLI_REQUIREMENT, "interactive-cli", Path(td))
            self.assertIsNone(result.runner_integration)
            self.assertFalse((result.project_root / ".project/runner").exists())
            lock = json.loads((result.project_root / "project.lock.json").read_text(encoding="utf-8"))
            self.assertIsNone(lock["runner_integration"])
            self.assertNotIn("long_running_execution", lock["capabilities"])

    def test_long_running_project_materializes_plan_only_runner(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            result = generate_project(
                PYTHON_CLI_REQUIREMENT,
                "long-cli",
                Path(td),
                intent=IntentSnapshot(autonomy="long-running"),
            )
            self.assertIsNotNone(result.runner_integration)
            root = result.project_root
            for relative in (
                RUNNER_PLAN_PATH,
                RUNNER_CONTRACT_PATH,
                RUNNER_README_PATH,
                RUNNER_STATE_README_PATH,
                RUNNER_EVIDENCE_PATH,
            ):
                self.assertTrue((root / relative).is_file(), relative)
            self.assertFalse((root / RUNNER_ADMISSION_LOCK_PATH).exists())
            lock = json.loads((root / "project.lock.json").read_text(encoding="utf-8"))
            self.assertIn("long_running_execution", lock["capabilities"])
            self.assertEqual(lock["runner_integration"]["provider"]["id"], "dagu")
            self.assertFalse(lock["runner_integration"]["runtime_verified"])
            evidence = json.loads((root / RUNNER_EVIDENCE_PATH).read_text(encoding="utf-8"))
            self.assertEqual(evidence["status"], "PARTIALLY_VERIFIED")
            self.assertFalse(evidence["runtime"].get("runtime_verified", True))
            serialized = (root / RUNNER_PLAN_PATH).read_text(encoding="utf-8")
            self.assertNotIn("aionui", serialized.casefold())
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["runner_integration"]["status"], "PARTIALLY_VERIFIED")
            self.assertFalse(restored["runner_integration"]["runtime_verified"])

    def test_explicit_runner_requires_long_running_intent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            output = Path(td)
            with self.assertRaisesRegex(FactoryError, "requires Intent autonomy='long-running'"):
                generate_project(PYTHON_CLI_REQUIREMENT, "bad-runner-cli", output, runner="dagu")
            self.assertFalse((output / "bad-runner-cli").exists())
            self.assertFalse((output / "bad-runner-cli.zip").exists())

    def test_runner_harness_must_be_materialized(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(FactoryError, "not among the materialized harnesses"):
                generate_project(
                    PYTHON_CLI_REQUIREMENT,
                    "runner-harness-cli",
                    Path(td),
                    intent=IntentSnapshot(autonomy="long-running"),
                    harnesses=("codex",),
                    runner_harness="claude",
                )

    def test_runner_plan_tamper_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            result = generate_project(
                PYTHON_CLI_REQUIREMENT,
                "tamper-runner-cli",
                Path(td),
                intent=IntentSnapshot(autonomy="long-running"),
            )
            lock = json.loads((result.project_root / "project.lock.json").read_text(encoding="utf-8"))
            plan_path = result.project_root / RUNNER_PLAN_PATH
            plan_path.write_text(plan_path.read_text(encoding="utf-8") + "\n# tampered\n", encoding="utf-8")
            check = verify_runner_materialization(result.project_root, lock["runner_integration"])
            self.assertEqual(check["status"], "FAILED")
            self.assertTrue(any("hash differs" in item for item in check["failures"]))

    def test_secret_does_not_enter_runner_plan(self) -> None:
        secret = "sk-runner-secret-1234567890"
        with tempfile.TemporaryDirectory() as td:
            result = generate_project(
                f"做一个 Python 命令行工具。API_KEY={secret}，不能覆盖原始文件。",
                "secret-runner-cli",
                Path(td),
                intent=IntentSnapshot(autonomy="long-running"),
            )
            for relative in (RUNNER_PLAN_PATH, RUNNER_CONTRACT_PATH, RUNNER_EVIDENCE_PATH):
                self.assertNotIn(secret, (result.project_root / relative).read_text(encoding="utf-8"))


class FakeDaguContractLabTests(unittest.TestCase):
    def _generate_long_runner(self, root: Path, name: str = "fake-dagu-cli"):
        return generate_project(
            PYTHON_CLI_REQUIREMENT,
            name,
            root,
            intent=IntentSnapshot(autonomy="long-running"),
        )

    def test_fake_runtime_validate_dry_start_status_stop_order(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            result = self._generate_long_runner(base / "out")
            env, log_path = _write_fake_dagu(base)
            lock = json.loads((result.project_root / "project.lock.json").read_text(encoding="utf-8"))
            plan_sha = lock["runner_integration"]["plan"]["sha256"]

            probe = probe_runner_runtime(resolve_runner("dagu"), env=env)
            self.assertEqual(probe["status"], "AVAILABLE_UNVALIDATED")
            self.assertEqual(probe["version"], "2.11.2")

            validation = validate_runner_runtime(result.project_root, env=env)
            self.assertEqual(validation["status"], "DRY_VERIFIED")
            self.assertFalse(validation["runtime_verified"])

            started = start_runner(
                result.project_root,
                confirm_plan_sha256=plan_sha,
                run_id="run-001",
                env=env,
            )
            self.assertEqual(started["status"], "START_COMMAND_COMPLETED")
            self.assertTrue(started["start_command_succeeded"])
            self.assertFalse(started["workflow_completion_verified"])
            self.assertFalse(started["runtime_verified"])

            status = runner_status(result.project_root, run_id="run-001", env=env)
            stopped = stop_runner(result.project_root, run_id="run-001", env=env)
            self.assertEqual(status["status"], "EXECUTED")
            self.assertEqual(stopped["status"], "EXECUTED")

            lines = log_path.read_text(encoding="utf-8").splitlines()
            # probe + validate/dry; start performs its own validate/dry preflight + version probe.
            self.assertIn("version", lines[0])
            self.assertTrue(any(line.startswith("validate ") for line in lines))
            self.assertTrue(any(line.startswith("dry ") for line in lines))
            start_index = next(i for i, line in enumerate(lines) if line.startswith("start "))
            validate_indices = [i for i, line in enumerate(lines[:start_index]) if line.startswith("validate ")]
            dry_indices = [i for i, line in enumerate(lines[:start_index]) if line.startswith("dry ")]
            self.assertTrue(validate_indices)
            self.assertTrue(dry_indices)
            self.assertLess(max(validate_indices), start_index)
            self.assertLess(max(dry_indices), start_index)
            self.assertTrue(any(line.startswith("status ") for line in lines[start_index + 1 :]))
            self.assertTrue(any(line.startswith("stop ") for line in lines[start_index + 1 :]))

    def test_wrong_plan_hash_blocks_before_runtime_call(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            result = self._generate_long_runner(base / "out", "bad-hash-cli")
            env, log_path = _write_fake_dagu(base)
            with self.assertRaisesRegex(RunnerError, "confirmation hash"):
                start_runner(result.project_root, confirm_plan_sha256="0" * 64, run_id="run-1", env=env)
            self.assertFalse(log_path.exists())

    def test_validate_failure_blocks_start(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            result = self._generate_long_runner(base / "out", "validate-fail-cli")
            env, log_path = _write_fake_dagu(base, fail_validate=True)
            lock = json.loads((result.project_root / "project.lock.json").read_text(encoding="utf-8"))
            with self.assertRaisesRegex(RunnerError, "validate failed"):
                start_runner(
                    result.project_root,
                    confirm_plan_sha256=lock["runner_integration"]["plan"]["sha256"],
                    run_id="run-2",
                    env=env,
                )
            lines = log_path.read_text(encoding="utf-8").splitlines()
            self.assertFalse(any(line.startswith("start ") for line in lines))

    def test_invalid_run_id_blocks_before_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            result = self._generate_long_runner(base / "out", "bad-runid-cli")
            env, log_path = _write_fake_dagu(base)
            lock = json.loads((result.project_root / "project.lock.json").read_text(encoding="utf-8"))
            with self.assertRaisesRegex(RunnerError, "run_id"):
                start_runner(
                    result.project_root,
                    confirm_plan_sha256=lock["runner_integration"]["plan"]["sha256"],
                    run_id="bad run id; rm -rf /",
                    env=env,
                )
            self.assertFalse(log_path.exists())

    def test_same_project_admission_lock_blocks_second_factory_start(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with _project_admission_lock(root):
                with self.assertRaisesRegex(RunnerError, "already active"):
                    with _project_admission_lock(root):
                        self.fail("second same-project admission lock unexpectedly succeeded")
            self.assertTrue((root / RUNNER_ADMISSION_LOCK_PATH).is_file())


if __name__ == "__main__":
    unittest.main()
