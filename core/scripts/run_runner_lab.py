from __future__ import annotations

import argparse
import json
import os
import stat
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from project_factory.decision import IntentSnapshot  # noqa: E402
from project_factory.factory import generate_project  # noqa: E402
from project_factory.runner import (  # noqa: E402
    RunnerError,
    runner_status,
    start_runner,
    stop_runner,
    validate_runner_runtime,
)


def write_fake_dagu(bin_dir: Path, log_path: Path) -> Path:
    path = bin_dir / "dagu"
    script = f'''#!/usr/bin/env python3
import json, sys
from pathlib import Path
log = Path({str(log_path)!r})
args = sys.argv[1:]
with log.open("a", encoding="utf-8") as f:
    f.write(json.dumps(args) + "\\n")
if args and args[0] == "version":
    print("dagu version 2.11.2")
    raise SystemExit(0)
if args and args[0] in {{"validate", "dry", "start", "status", "stop"}}:
    print(json.dumps({{"fake": True, "argv": args}}))
    raise SystemExit(0)
raise SystemExit(2)
'''
    path.write_text(script, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run controlled fake-Dagu adapter lab; never counts as live Dagu runtime evidence")
    parser.add_argument("--evidence", required=True, type=Path)
    args = parser.parse_args()

    if os.name == "nt":
        raise SystemExit("This evidence helper is POSIX-only; unit tests cover platform-neutral contract behavior.")

    with tempfile.TemporaryDirectory(prefix="project-factory-p11-runner-lab-") as td:
        temp = Path(td)
        out = temp / "out"
        bin_dir = temp / "bin"
        bin_dir.mkdir()
        log = temp / "fake-dagu.log"
        write_fake_dagu(bin_dir, log)
        env = dict(os.environ)
        env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")

        generated = generate_project(
            "做一个 Python CLI 工具。",
            "runner-lab-cli",
            out,
            intent=IntentSnapshot(autonomy="long-running"),
            harnesses=("codex",),
            runner="dagu",
            runner_harness="codex",
            process_env=env,
        )
        project = generated.project_root
        runner_lock = json.loads((project / "project.lock.json").read_text(encoding="utf-8"))["runner_integration"]
        plan_sha = runner_lock["plan"]["sha256"]
        preflight = validate_runner_runtime(project, env=env)
        started = start_runner(project, confirm_plan_sha256=plan_sha, run_id="lab-run-001", env=env)
        status = runner_status(project, run_id="lab-run-001", env=env)
        stopped = stop_runner(project, run_id="lab-run-001", env=env)
        wrong_hash_blocked = False
        try:
            start_runner(project, confirm_plan_sha256="0" * 64, run_id="lab-run-bad", env=env)
        except RunnerError:
            wrong_hash_blocked = True
        calls = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
        commands = [item[0] for item in calls if item]
        for required in ("version", "validate", "dry", "start", "status", "stop"):
            if required not in commands:
                raise SystemExit(f"fake Dagu lab missing command {required}: {calls!r}")
        if not wrong_hash_blocked:
            raise SystemExit("wrong plan hash did not block before Runner start")

        evidence = {
            "status": "PASS",
            "provider_fixture": "CONTROLLED_FAKE_DAGU",
            "fake_reported_version": "2.11.2",
            "preflight_status": preflight["status"],
            "start_status": started["status"],
            "status_command": status["command_result"]["returncode"],
            "stop_command": stopped["command_result"]["returncode"],
            "wrong_plan_hash_blocked": True,
            "observed_call_sequence": calls,
            "runtime_verified": False,
            "truth_boundary": "This proves Project Factory adapter ordering/fail-closed behavior only. It is not live Dagu runtime evidence.",
        }
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
