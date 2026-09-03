from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import random
import stat
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from project_factory.factory import FactoryError, _safe_project_name, restore_verify_project_zip, verify_project_manifest  # noqa: E402
from project_factory.normalizer import MAX_REQUIREMENT_CHARS, normalize_requirement  # noqa: E402
from project_factory.recovery import RecoveryError, apply_checkpoint_restore, inspect_checkpoint, plan_checkpoint_restore  # noqa: E402
from project_factory.ux import check_project  # noqa: E402


def _env() -> dict[str, str]:
    env = dict(os.environ)
    current = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(ROOT / "src") + ((os.pathsep + current) if current else "")
    return env


def _run(argv: list[str], *, cwd: Path = ROOT, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        env=_env(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=timeout,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _make_checkpoint(path: Path) -> None:
    payload = b"brutal recovery payload\n"
    digest = hashlib.sha256(payload).hexdigest()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("checkpoint-root/payload.txt", payload)
        zf.writestr("checkpoint-root/MANIFEST.sha256", f"{digest}  payload.txt\n")
        zf.writestr("checkpoint-root/CHECKPOINT_P12_COMPLETE.md", "brutal\n")


def shard_cli() -> dict[str, Any]:
    help_result = _run([sys.executable, "-m", "project_factory", "--help"], timeout=30)
    empty_result = _run([sys.executable, "-m", "project_factory"], timeout=30)
    status_result = _run([sys.executable, "-m", "project_factory", "status", "--json"], timeout=60)
    legacy_result = _run([
        sys.executable,
        "-m",
        "project_factory",
        "validate",
        "fixtures/golden/01_tiny_python_tool.yaml",
        "--json",
    ], timeout=30)
    status = json.loads(status_result.stdout)
    checks = {
        "help_rc": help_result.returncode == 0,
        "empty_rc": empty_result.returncode == 0,
        "human_path_visible": "status -> new -> check -> verify" in help_result.stdout,
        "empty_is_help": "status -> new -> check -> verify" in empty_result.stdout,
        "status_ready": status_result.returncode == 0 and status.get("status") in {"READY", "READY_WITH_WARNINGS"},
        "legacy_validate": legacy_result.returncode == 0,
    }
    return {"status": "PASS" if all(checks.values()) else "FAILED", "checks": checks}


def shard_archive() -> dict[str, Any]:
    cases: dict[str, bool] = {}
    with tempfile.TemporaryDirectory(prefix="pf-brutal-archive-") as td:
        root = Path(td)
        traversal = root / "traversal.zip"
        with zipfile.ZipFile(traversal, "w") as zf:
            zf.writestr("../escape.txt", "no")
        try:
            restore_verify_project_zip(traversal)
            cases["project_parent_traversal"] = False
        except FactoryError:
            cases["project_parent_traversal"] = True

        backslash = root / "backslash.zip"
        with zipfile.ZipFile(backslash, "w") as zf:
            zf.writestr("root\\..\\escape.txt", "no")
        try:
            restore_verify_project_zip(backslash)
            cases["project_backslash_traversal"] = False
        except FactoryError:
            cases["project_backslash_traversal"] = True

        symlink = root / "symlink.zip"
        info = zipfile.ZipInfo("root/link")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        with zipfile.ZipFile(symlink, "w") as zf:
            zf.writestr(info, "../../outside")
        try:
            restore_verify_project_zip(symlink)
            cases["project_symlink"] = False
        except FactoryError:
            cases["project_symlink"] = True

        checkpoint = root / "checkpoint-backslash.zip"
        with zipfile.ZipFile(checkpoint, "w") as zf:
            zf.writestr("root\\..\\escape.txt", "no")
        try:
            inspect_checkpoint(checkpoint)
            cases["checkpoint_backslash_traversal"] = False
        except RecoveryError:
            cases["checkpoint_backslash_traversal"] = True

        project = root / "project"
        project.mkdir()
        outside = root / "outside.txt"
        outside.write_text("outside", encoding="utf-8")
        digest = _sha256(outside)
        (project / "PROJECT_MANIFEST.sha256").write_text(f"{digest}  ../outside.txt\n", encoding="utf-8")
        ok, failures = verify_project_manifest(project)
        cases["manifest_parent_traversal"] = not ok and bool(failures)
    return {"status": "PASS" if all(cases.values()) else "FAILED", "cases": cases}


def shard_overwrite() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="pf-brutal-overwrite-") as td:
        out = Path(td) / "out"
        first = _run([
            sys.executable, "-m", "project_factory", "new", "repeat-safe", "做一个 Python 命令行工具。",
            "--out", str(out), "--json",
        ], timeout=120)
        if first.returncode != 0:
            return {"status": "FAILED", "reason": "first generation failed", "output": first.stdout[-4000:]}
        payload = json.loads(first.stdout)
        project = Path(payload["project"])
        archive = Path(payload["zip"])
        before = {"lock": _sha256(project / "project.lock.json"), "zip": _sha256(archive)}
        second = _run([
            sys.executable, "-m", "project_factory", "new", "repeat-safe", "做一个 Python 命令行工具。",
            "--out", str(out), "--json",
        ], timeout=60)
        after = {"lock": _sha256(project / "project.lock.json"), "zip": _sha256(archive)}
        checked = check_project(project)
        checks = {
            "first_success": first.returncode == 0,
            "second_blocked": second.returncode == 4,
            "second_reports_overwrite_refusal": "overwrite" in second.stdout.casefold(),
            "project_unchanged": before == after,
            "project_still_checks": checked["status"] == "PASS",
        }
        return {"status": "PASS" if all(checks.values()) else "FAILED", "checks": checks}


def shard_concurrency() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="pf-brutal-concurrency-") as td:
        out = Path(td) / "out"
        base = [sys.executable, "-m", "project_factory", "new", "race-safe", "做一个 Python 命令行工具。", "--out", str(out), "--json"]
        processes = [
            subprocess.Popen(base, cwd=ROOT, env=_env(), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            for _ in range(2)
        ]
        results: list[tuple[int, str]] = []
        for process in processes:
            try:
                stdout, _ = process.communicate(timeout=120)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, _ = process.communicate(timeout=10)
                results.append((124, stdout or ""))
            else:
                results.append((int(process.returncode or 0), stdout or ""))
        codes = sorted(code for code, _ in results)
        project = out / "race-safe"
        archive = out / "race-safe.zip"
        checked = check_project(project) if project.is_dir() else {"status": "MISSING"}

        unique_processes = []
        for name in ("parallel-a", "parallel-b"):
            argv = [sys.executable, "-m", "project_factory", "new", name, "做一个 Python 命令行工具。", "--out", str(out), "--json"]
            unique_processes.append(subprocess.Popen(argv, cwd=ROOT, env=_env(), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT))
        unique_codes = []
        for process in unique_processes:
            try:
                process.communicate(timeout=120)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=10)
                unique_codes.append(124)
            else:
                unique_codes.append(int(process.returncode or 0))

        checks = {
            "same_name_exactly_one_winner": codes == [0, 4],
            "same_name_project_integrity": checked["status"] == "PASS",
            "same_name_zip_exists": archive.is_file(),
            "different_names_parallel_success": unique_codes == [0, 0],
            "parallel_a_integrity": check_project(out / "parallel-a")["status"] == "PASS",
            "parallel_b_integrity": check_project(out / "parallel-b")["status"] == "PASS",
        }
        return {"status": "PASS" if all(checks.values()) else "FAILED", "checks": checks, "same_name_codes": codes, "unique_codes": unique_codes}


def _load_release_gate_module() -> Any:
    path = ROOT / "scripts" / "run_release_gate.py"
    spec = importlib.util.spec_from_file_location("pf_release_gate_brutal", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load release gate module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def shard_timeout() -> dict[str, Any]:
    gate = _load_release_gate_module()
    with tempfile.TemporaryDirectory(prefix="pf-brutal-timeout-") as td:
        log = Path(td) / "timeout.log"
        code = (
            "import subprocess,sys,time; "
            "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
            "print(p.pid, flush=True); time.sleep(60)"
        )
        started = time.monotonic()
        result = gate.run_gate("forced-timeout", [sys.executable, "-c", code], stdout_path=log, timeout_sec=1)
        elapsed = time.monotonic() - started
        text = log.read_text(encoding="utf-8")
        child_dead = True
        if os.name == "posix":
            first = text.strip().splitlines()[0] if text.strip() else ""
            if first.isdigit():
                pid = int(first)
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    child_dead = True
                else:
                    child_dead = False
        checks = {
            "bounded_elapsed": elapsed < 8,
            "timeout_status_failed": result["status"] == "FAILED",
            "timeout_returncode": result["returncode"] == 124,
            "timeout_recorded": result["timed_out"] is True,
            "timeout_log_recorded": "TIMEOUT" in text,
            "grandchild_terminated": child_dead,
        }
        return {"status": "PASS" if all(checks.values()) else "FAILED", "checks": checks, "elapsed_sec": round(elapsed, 3), "gate": result}


def shard_recovery() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="pf-brutal-recovery-") as td:
        root = Path(td)
        archive = root / "checkpoint.zip"
        _make_checkpoint(archive)
        inspect = inspect_checkpoint(archive)
        dest = root / "restore"
        plan = plan_checkpoint_restore(archive, dest)
        wrong_hash_blocked = False
        try:
            apply_checkpoint_restore(archive, dest, confirm_plan_sha256="0" * 64)
        except RecoveryError:
            wrong_hash_blocked = not dest.exists()
        restored = apply_checkpoint_restore(archive, dest, confirm_plan_sha256=plan.plan_sha256)
        repeat_blocked = False
        try:
            plan_checkpoint_restore(archive, dest)
        except RecoveryError:
            repeat_blocked = True
        checks = {
            "inspect_verified": inspect["status"] == "VERIFIED",
            "wrong_hash_no_destination": wrong_hash_blocked,
            "restore_verified": restored["status"] == "RESTORED" and restored["manifest"]["status"] == "PASS",
            "repeat_restore_blocked": repeat_blocked,
        }
        return {"status": "PASS" if all(checks.values()) else "FAILED", "checks": checks}


def shard_repetition() -> dict[str, Any]:
    target = ROOT / "golden_outputs" / "json-batch-cli"
    before = _sha256(target / "project.lock.json")
    check_statuses = [check_project(target)["status"] for _ in range(25)]
    after = _sha256(target / "project.lock.json")
    status_codes = []
    for _ in range(5):
        result = _run([sys.executable, "-m", "project_factory", "status", "--json"], timeout=60)
        status_codes.append(result.returncode)
    checks = {
        "25_read_only_checks_pass": set(check_statuses) == {"PASS"},
        "check_did_not_mutate_lock": before == after,
        "5_status_runs_pass": status_codes == [0, 0, 0, 0, 0],
    }
    return {"status": "PASS" if all(checks.values()) else "FAILED", "checks": checks}


def shard_fuzz() -> dict[str, Any]:
    random.seed(20260830)
    invalid = ["", "../x", "a/b", "a\\b", "中文项目", "x" * 300, "ends-", "ends_"]
    invalid_blocked = 0
    for value in invalid:
        try:
            _safe_project_name(value)
        except FactoryError:
            invalid_blocked += 1

    middle = "abcdefghijklmnopqrstuvwxyz0123456789-_"
    tail = "abcdefghijklmnopqrstuvwxyz0123456789"
    valid_names = [
        "p" + "".join(random.choice(middle) for _ in range(random.randint(0, 31))) + random.choice(tail)
        for _ in range(200)
    ]
    valid_ok = sum(1 for name in valid_names if _safe_project_name(name) == name)

    oversized_started = time.monotonic()
    oversized_blocked = False
    try:
        normalize_requirement("x" * (MAX_REQUIREMENT_CHARS + 1))
    except ValueError:
        oversized_blocked = True
    oversized_elapsed = time.monotonic() - oversized_started

    with tempfile.TemporaryDirectory(prefix="pf-brutal-fuzz-") as td:
        project = Path(td)
        fuzz_failures = 0
        for index in range(200):
            raw = random.choice(["../", "..\\", "/abs/", "C:\\", "safe/"]) + "x" * random.randint(1, 20)
            (project / "PROJECT_MANIFEST.sha256").write_text("0" * 64 + "  " + raw + "\n", encoding="utf-8")
            ok, _ = verify_project_manifest(project)
            if ok:
                fuzz_failures += 1
    checks = {
        "invalid_names_blocked": invalid_blocked == len(invalid),
        "200_valid_names_accepted": valid_ok == len(valid_names),
        "oversized_requirement_blocked_fast": oversized_blocked and oversized_elapsed < 1.0,
        "manifest_fuzz_never_false_passed": fuzz_failures == 0,
    }
    return {"status": "PASS" if all(checks.values()) else "FAILED", "checks": checks, "oversized_elapsed_sec": round(oversized_elapsed, 6)}


SHARDS: dict[str, Callable[[], dict[str, Any]]] = {
    "cli": shard_cli,
    "archive": shard_archive,
    "overwrite": shard_overwrite,
    "concurrency": shard_concurrency,
    "timeout": shard_timeout,
    "recovery": shard_recovery,
    "repetition": shard_repetition,
    "fuzz": shard_fuzz,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Bounded destructive-but-temporary Project Factory brutal suite")
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--resume", action="store_true", help="Reuse only shard files with explicit PASS status")
    parser.add_argument("--shard", action="append", choices=sorted(SHARDS), help="Run only selected shard(s)")
    args = parser.parse_args()
    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    selected = args.shard or list(SHARDS)
    results: list[dict[str, Any]] = []
    for name in selected:
        shard_path = work / f"{name}.json"
        if args.resume and shard_path.is_file():
            try:
                cached = json.loads(shard_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                cached = {}
            if cached.get("status") == "PASS":
                cached["reused"] = True
                results.append(cached)
                continue
        started = time.monotonic()
        try:
            detail = SHARDS[name]()
        except Exception as exc:
            detail = {"status": "FAILED", "error": f"{type(exc).__name__}: {exc}"}
        detail = {"name": name, **detail, "elapsed_sec": round(time.monotonic() - started, 3), "reused": False}
        shard_path.write_text(json.dumps(detail, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        results.append(detail)
    failures = [item["name"] for item in results if item.get("status") != "PASS"]
    evidence = {
        "status": "PASS" if not failures else "FAILED",
        "suite": "project-factory-brutal",
        "selected_shards": selected,
        "passed": len(results) - len(failures),
        "total": len(results),
        "failed_shards": failures,
        "results": results,
        "persistent_business_data_modified": False,
        "temporary_destructive_actions_only": True,
        "automatic_delete_of_user_data": False,
    }
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
