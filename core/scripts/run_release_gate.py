from __future__ import annotations

import argparse
import json
import os
import re
import signal
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _env() -> dict[str, str]:
    env = dict(os.environ)
    current = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(ROOT / "src") + ((os.pathsep + current) if current else "")
    return env


def _terminate_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    else:
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=10,
        )
        if process.poll() is None:
            process.kill()


def run_gate(name: str, argv: list[str], *, stdout_path: Path, timeout_sec: int) -> dict:
    started = time.monotonic()
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    process = subprocess.Popen(
        argv,
        cwd=ROOT,
        env=_env(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=os.name == "posix",
        creationflags=creationflags,
    )
    timed_out = False
    try:
        stdout, _ = process.communicate(timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        timed_out = True
        _terminate_process_tree(process)
        try:
            stdout, _ = process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            stdout = ""
            if process.stdout is not None:
                process.stdout.close()
        if process.poll() is None:
            process.kill()
    returncode = 124 if timed_out else int(process.returncode or 0)
    stdout = stdout or ""
    if timed_out:
        stdout += f"\n[release-gate] TIMEOUT after {timeout_sec}s; process tree terminated.\n"
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stdout_path.write_text(stdout, encoding="utf-8")
    return {
        "name": name,
        "status": "PASS" if returncode == 0 else "FAILED",
        "returncode": returncode,
        "elapsed_sec": round(time.monotonic() - started, 3),
        "stdout": str(stdout_path),
        "reused": False,
        "timed_out": timed_out,
        "timeout_sec": timeout_sec,
    }


def _json_status(path: Path, accepted: set[str]) -> bool:
    if not path.is_file():
        return False
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    return value.get("status") in accepted


def reuse_gate(name: str, log: Path, evidence: Path | None, accepted: set[str]) -> dict | None:
    if name == "tests":
        if not log.is_file():
            return None
        text = log.read_text(encoding="utf-8")
        match = re.search(r"Ran (\d+) tests", text)
        if "\nOK\n" not in text or match is None:
            return None
        return {"name": name, "status": "PASS", "returncode": 0, "elapsed_sec": None, "stdout": str(log), "reused": True, "test_count": int(match.group(1))}
    if name == "doctor-deep":
        if not log.is_file():
            return None
        try:
            value = json.loads(log.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        if value.get("status") == "BLOCKED" or value.get("deep_smoke", {}).get("status") != "PASS":
            return None
        return {"name": name, "status": "PASS", "returncode": 0, "elapsed_sec": None, "stdout": str(log), "reused": True, "doctor_status": value.get("status")}
    if evidence is not None and _json_status(evidence, accepted):
        return {"name": name, "status": "PASS", "returncode": 0, "elapsed_sec": None, "stdout": str(log), "evidence": str(evidence), "reused": True}
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Project Factory release gate: existing spines + human UX + brutal safety boundaries")
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--resume", action="store_true", help="Reuse only gates whose explicit PASS evidence already exists")
    args = parser.parse_args()
    work = args.work_dir.resolve()
    if work.exists() and any(work.iterdir()) and not args.resume:
        raise SystemExit(f"Refusing to overwrite non-empty release-gate directory without --resume: {work}")
    work.mkdir(parents=True, exist_ok=True)
    logs = work / "logs"
    outputs = work / "outputs"
    outputs.mkdir(exist_ok=True)

    specs = [
        ("tests", [sys.executable, "scripts/run_tests.py"], logs / "tests.txt", None, {"PASS"}, 300),
        ("doctor-deep", [sys.executable, "-m", "project_factory", "doctor", "--deep"], logs / "doctor.txt", None, {"PASS"}, 240),
        ("compatibility-refresh", [sys.executable, "scripts/run_compatibility_refresh.py", "--evidence", str(outputs / "compatibility.json")], logs / "compatibility.txt", outputs / "compatibility.json", {"PASS"}, 180),
        ("golden-matrix", [sys.executable, "scripts/run_golden_matrix.py", "--output-dir", str(outputs / "goldens"), "--evidence", str(outputs / "golden.json")], logs / "golden.txt", outputs / "golden.json", {"VERIFIED"}, 300),
        ("runner-matrix", [sys.executable, "scripts/run_runner_matrix.py", "--output-dir", str(outputs / "runners"), "--evidence", str(outputs / "runner.json")], logs / "runner.txt", outputs / "runner.json", {"PASS"}, 300),
        ("upgrade-matrix", [sys.executable, "scripts/run_upgrade_matrix.py", "--source-goldens", str(ROOT / "golden_outputs"), "--source-stage", "P12", "--work-dir", str(outputs / "upgrade"), "--evidence", str(outputs / "upgrade.json")], logs / "upgrade.txt", outputs / "upgrade.json", {"PASS"}, 300),
        ("product-dogfood", [sys.executable, "scripts/run_product_dogfood.py", "--work-dir", str(outputs / "dogfood"), "--evidence", str(outputs / "dogfood.json")], logs / "dogfood.txt", outputs / "dogfood.json", {"PASS"}, 300),
        ("wheel-smoke", [sys.executable, "scripts/run_factory_wheel_smoke.py", "--evidence", str(outputs / "wheel.json")], logs / "wheel.txt", outputs / "wheel.json", {"PASS"}, 300),
        ("brutal-suite", [sys.executable, "scripts/run_brutal_suite.py", "--work-dir", str(outputs / "brutal"), "--evidence", str(outputs / "brutal.json"), "--resume"], logs / "brutal.txt", outputs / "brutal.json", {"PASS"}, 240),
    ]

    gates = []
    for name, argv, log, evidence_path, accepted, timeout_sec in specs:
        reused = reuse_gate(name, log, evidence_path, accepted) if args.resume else None
        gates.append(reused or run_gate(name, argv, stdout_path=log, timeout_sec=timeout_sec))
        if gates[-1]["status"] != "PASS":
            break

    expected_names = [item[0] for item in specs]
    completed_names = [gate["name"] for gate in gates]
    missing = [name for name in expected_names if name not in completed_names]
    failed = [gate["name"] for gate in gates if gate["status"] != "PASS"]
    external = {
        "dagu": bool(shutil.which("dagu")),
        "codex": bool(shutil.which("codex")),
        "claude": bool(shutil.which("claude")),
    }
    evidence = {
        "status": "PASS" if not failed and not missing else "FAILED",
        "resume_mode": args.resume,
        "gates": gates,
        "failed_gates": failed,
        "missing_gates": missing,
        "external_live_runner_gate": {
            "status": "AVAILABLE_FOR_MANUAL_LIVE_DOGFOOD" if external["dagu"] and (external["codex"] or external["claude"]) else "UNVERIFIED_ENVIRONMENT_UNAVAILABLE",
            "runtime_presence": external,
            "automatic_execution": False,
            "note": "Release gate never auto-starts an unattended Agent shift. Live runtime dogfood requires an explicitly verified Dagu + authenticated Harness environment.",
        },
        "environment_modified": False,
        "network_required": False,
    }
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0 if evidence["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
