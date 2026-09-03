"""
Gate 5 — Normal Close Hard Gate Test
=====================================
Implements the exact predicate from 04_NORMAL_CLOSE_HARD_GATE.md:

  normal_close_pass =
      close_request_succeeded
      AND app_exited_before_fallback
      AND owned_runtime_count == 0
      AND app_lockprobe_pass

If app_exited_before_fallback is False the gate is FAIL regardless of
whether cleanup later succeeds.  A force-kill fallback is only used AFTER
the gate has been marked FAIL, to leave the machine clean.

Usage:
    python test_lifecycle_gate5.py [--exe PATH] [--timeout-s N] [--out FILE]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_TIMEOUT_S = 8          # seconds to wait before declaring fallback needed
STABLE_WAIT_S     = 5          # seconds to let the app reach a stable state
RUNTIME_SETTLE_S  = 0.5        # extra settle after close request
EXE_DEFAULT       = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "ProjectFactory" / "app" / "ProjectFactory.exe"

# ---------------------------------------------------------------------------

def log(msg: str, out_lines: list[str]) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    out_lines.append(line)


def find_owned_runtime_procs(install_root: Path) -> list[dict]:
    """Return running process info for PIDs whose exe is inside install_root."""
    try:
        result = subprocess.run(
            ["powershell", "-NonInteractive", "-NoProfile", "-Command",
             "Get-Process | Select-Object Id,ProcessName,@{N='Path';E={try{$_.MainModule.FileName}catch{''}}} | ConvertTo-Json -Compress"],
            capture_output=True, text=True, timeout=15
        )
        procs = json.loads(result.stdout) if result.stdout.strip() else []
        if isinstance(procs, dict):
            procs = [procs]
        root_str = str(install_root).lower().rstrip("\\/")
        return [p for p in procs if str(p.get("Path", "")).lower().startswith(root_str)]
    except Exception as exc:
        print(f"WARN find_owned_runtime_procs failed: {exc}", file=sys.stderr)
        return []


def lock_probe(app_dir: Path) -> tuple[bool, str]:
    """Try rename-and-restore on app_dir to probe for file locks.
    Returns (pass, detail).
    """
    if not app_dir.exists():
        return True, f"app_dir absent ({app_dir}) -- treated as unlocked (uninstalled)"
    tmp = app_dir.parent / (app_dir.name + "_lockprobe_tmp")
    try:
        app_dir.rename(tmp)
        tmp.rename(app_dir)
        return True, f"rename-and-restore OK on {app_dir}"
    except Exception as exc:
        # Attempt rollback
        try:
            if tmp.exists():
                tmp.rename(app_dir)
        except Exception:
            pass
        return False, f"rename failed: {exc}"


def snapshot_processes(install_root: Path, label: str, out_lines: list[str]) -> list[dict]:
    procs = find_owned_runtime_procs(install_root)
    log(f"SNAPSHOT [{label}] owned_process_count={len(procs)}", out_lines)
    for p in procs:
        log(f"  PID={p.get('Id')} Name={p.get('ProcessName')} Path={p.get('Path')}", out_lines)
    return procs


def is_project_factory_exe(path: str, exe: Path) -> bool:
    return Path(path or "").resolve() == exe.resolve() if path else False


def is_owned_runtime_python(path: str, install_root: Path) -> bool:
    if not path:
        return False
    lowered = str(path).lower().replace("/", "\\")
    root = str(install_root).lower().rstrip("\\")
    return lowered.startswith(root) and "\\.pf_runtime\\" in lowered and lowered.endswith("\\python.exe")


def live_bridge_from_procs(procs: list[dict], exe: Path, install_root: Path) -> tuple[bool, bool, list[str]]:
    app_seen = any(is_project_factory_exe(str(p.get("Path", "")), exe) for p in procs)
    python_paths = [str(p.get("Path", "")) for p in procs if is_owned_runtime_python(str(p.get("Path", "")), install_root)]
    return app_seen, bool(python_paths), python_paths


def try_invoke_tools_refresh(out_lines: list[str]) -> str:
    """Best-effort UI Automation: HomePage status may have already finished.
    Click 工具 then 刷新 to start another owned bridge process."""
    ps = r"""
Add-Type -AssemblyName UIAutomationClient
$root = [System.Windows.Automation.AutomationElement]::RootElement
$winCond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty, 'Project Factory')
$win = $root.FindFirst([System.Windows.Automation.TreeScope]::Children, $winCond)
if (-not $win) { $win = $root.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $winCond) }
if (-not $win) { Write-Output 'NO_WINDOW'; exit 0 }
function Invoke-ByName([string]$name) {
  $c = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty, $name)
  $el = $win.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $c)
  if (-not $el) { return 'missing' }
  try {
    $inv = $el.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
    $inv.Invoke()
    return 'invoked'
  } catch {
    try {
      $sel = $el.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern)
      $sel.Select()
      return 'selected'
    } catch { return 'no-pattern' }
  }
}
$tools = Invoke-ByName '工具'
Start-Sleep -Milliseconds 700
$refresh = Invoke-ByName '刷新'
Write-Output "tools=$tools refresh=$refresh"
"""
    try:
        result = subprocess.run(
            ["powershell", "-NonInteractive", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=20,
        )
        detail = (result.stdout or "").strip() or (result.stderr or "").strip() or f"exit={result.returncode}"
        log(f"UI_TRIGGER {detail}", out_lines)
        return detail
    except Exception as exc:
        log(f"UI_TRIGGER failed: {exc}", out_lines)
        return f"failed:{exc}"


def wait_for_live_bridge(install_root: Path, exe: Path, proc: subprocess.Popen, out_lines: list[str], timeout_s: float = 25.0) -> tuple[bool, list[dict], list[str]]:
    log(f"LIVE_BRIDGE_WAIT up to {timeout_s}s for ProjectFactory.exe + owned .pf_runtime python.exe ...", out_lines)
    deadline = time.monotonic() + timeout_s
    last: list[dict] = []
    python_paths: list[str] = []
    retriggered = False
    last_sig = ""
    next_heartbeat = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            log(f"FAIL: app exited during live-bridge wait (exit={proc.returncode})", out_lines)
            return False, last, python_paths
        last = find_owned_runtime_procs(install_root)
        sig = "|".join(sorted(f"{p.get('ProcessName')}:{p.get('Path')}" for p in last))
        if sig != last_sig:
            last_sig = sig
            snapshot_processes(install_root, "live_bridge_poll", out_lines)
        elif time.monotonic() >= next_heartbeat:
            log(f"LIVE_BRIDGE_WAIT still polling; owned={len(last)}", out_lines)
            next_heartbeat = time.monotonic() + 2.0
        app_seen, python_seen, python_paths = live_bridge_from_procs(last, exe, install_root)
        if app_seen and python_seen:
            log(f"LIVE_BRIDGE_OBSERVED python={python_paths}", out_lines)
            return True, last, python_paths
        remaining = deadline - time.monotonic()
        if (not retriggered) and remaining < (timeout_s * 0.55):
            retriggered = True
            try_invoke_tools_refresh(out_lines)
        time.sleep(0.12)
    log("LIVE_BRIDGE_NOT_OBSERVED within timeout", out_lines)
    snapshot_processes(install_root, "live_bridge_timeout", out_lines)
    return False, last, python_paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate 5 Normal Close Test")
    parser.add_argument("--exe", type=Path, default=EXE_DEFAULT)
    parser.add_argument("--timeout-s", type=float, default=DEFAULT_TIMEOUT_S)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    out_lines: list[str] = []
    log("=" * 70, out_lines)
    log("Gate 5 -- Normal Close Hard Gate Test", out_lines)
    log(f"exe={args.exe}", out_lines)
    log(f"close_timeout_s={args.timeout_s}", out_lines)
    log("=" * 70, out_lines)

    exe: Path = args.exe
    install_root: Path = exe.parent.parent  # <root>/app/ProjectFactory.exe -> <root>
    app_dir: Path = exe.parent              # <root>/app/

    # ------------------------------------------------------------------
    # Pre-flight
    # ------------------------------------------------------------------
    if not exe.is_file():
        log(f"PREFLIGHT FAIL: exe not found: {exe}", out_lines)
        _write_result(args.out, out_lines, False, "exe_not_found", {})
        return 1

    # ------------------------------------------------------------------
    # Step 1: Take before-start snapshot
    # ------------------------------------------------------------------
    before_procs = snapshot_processes(install_root, "before_launch", out_lines)

    # ------------------------------------------------------------------
    # Step 2: Launch the application
    # ------------------------------------------------------------------
    log(f"LAUNCH {exe}", out_lines)
    proc = subprocess.Popen([str(exe)])
    pid = proc.pid
    log(f"LAUNCH pid={pid}", out_lines)

    # ------------------------------------------------------------------
    # Step 3: Wait until a live owned Python bridge is actually running.
    # HomePage_Loaded invokes bridge "status"; that process is short-lived,
    # so we poll immediately instead of waiting 5s and missing it.
    # A UI-only ProjectFactory.exe tree is not a live-bridge gate.
    # ------------------------------------------------------------------
    live_bridge_observed, live_procs, live_python_paths = wait_for_live_bridge(
        install_root, exe, proc, out_lines, timeout_s=25.0
    )
    if proc.poll() is not None and not live_bridge_observed:
        _write_result(args.out, out_lines, False, "app_exited_during_live_bridge_wait", {
            "live_bridge_observed": False,
        })
        return 1

    # ------------------------------------------------------------------
    # Step 4: Capture before-close process tree WHILE bridge is live.
    # Reuse the observation snapshot so a short-lived status process is
    # not missed between poll-success and a second Get-Process call.
    # ------------------------------------------------------------------
    log("PRE_CLOSE snapshot ...", out_lines)
    if live_bridge_observed and live_procs:
        pre_close_procs = live_procs
        for p in pre_close_procs:
            log(f"  PID={p.get('Id')} Name={p.get('ProcessName')} Path={p.get('Path')}", out_lines)
    else:
        pre_close_procs = snapshot_processes(install_root, "pre_close", out_lines)
    app_seen, python_seen, python_paths = live_bridge_from_procs(pre_close_procs, exe, install_root)
    if python_seen:
        live_bridge_observed = True
        live_python_paths = python_paths
    if not live_bridge_observed:
        log("HARD BLOCK: pre_close did not contain ProjectFactory.exe + owned .pf_runtime python.exe", out_lines)
        log("A UI-only process tree cannot satisfy the live-bridge close gate.", out_lines)
        evidence = {
            "live_bridge_observed": False,
            "live_bridge_app_seen": app_seen,
            "live_bridge_python_seen": python_seen,
            "live_bridge_python_paths": live_python_paths,
            "before_procs": before_procs,
            "pre_close_procs": pre_close_procs,
            "fallback_invoked": False,
        }
        # Record FAIL first, then cleanup. Fallback must not convert to PASS.
        _write_result(args.out, out_lines, False, "live_bridge_not_observed", evidence)
        log("Gate 5 FAIL recorded. Beginning emergency cleanup (will NOT convert to PASS).", out_lines)
        _emergency_cleanup(proc, pid, install_root, out_lines)
        return 1

    # ------------------------------------------------------------------
    # Step 5: Send normal close (WM_CLOSE via CloseMainWindow equivalent)
    # ------------------------------------------------------------------
    log("CLOSE_REQUEST: sending CloseMainWindow via PowerShell ...", out_lines)
    close_result = subprocess.run(
        ["powershell", "-NonInteractive", "-NoProfile", "-Command",
         f"$p = Get-Process -Id {pid} -ErrorAction SilentlyContinue; "
         f"if ($p) {{ $p.CloseMainWindow() }} else {{ $false }}"],
        capture_output=True, text=True, timeout=10
    )
    close_stdout = close_result.stdout.strip()
    close_request_succeeded = close_stdout.lower() in ("true", "1")
    log(f"CloseMainWindow return: {close_stdout!r} -> close_request_succeeded={close_request_succeeded}", out_lines)

    # ------------------------------------------------------------------
    # Step 6: Wait for exit BEFORE any fallback
    # ------------------------------------------------------------------
    log(f"EXIT_WAIT: waiting up to {args.timeout_s}s for process to exit (no fallback yet) ...", out_lines)
    deadline = time.monotonic() + args.timeout_s
    app_exited_before_fallback = False
    exit_elapsed_s = None

    t_wait_start = time.monotonic()
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            exit_elapsed_s = time.monotonic() - t_wait_start
            app_exited_before_fallback = True
            break
        time.sleep(0.25)

    if app_exited_before_fallback:
        log(f"App process exited within {args.timeout_s}s: True (elapsed={exit_elapsed_s:.2f}s)", out_lines)
    else:
        log(f"App process exited within {args.timeout_s}s: False -- gate5_normal_close_pass=False", out_lines)

    # ------------------------------------------------------------------
    # Step 7: Check owned runtime count (only meaningful if app has exited)
    # ------------------------------------------------------------------
    time.sleep(RUNTIME_SETTLE_S)
    post_close_procs = snapshot_processes(install_root, "post_close", out_lines)
    owned_runtime_count = len(post_close_procs)
    log(f"owned_runtime_count={owned_runtime_count}", out_lines)

    # ------------------------------------------------------------------
    # Step 8: App directory lock probe
    # ------------------------------------------------------------------
    log(f"LOCK_PROBE: rename-and-restore {app_dir} ...", out_lines)
    lock_pass, lock_detail = lock_probe(app_dir)
    log(f"LOCK_PROBE result: {lock_pass} -- {lock_detail}", out_lines)

    # ------------------------------------------------------------------
    # Step 9: Evaluate gate predicate
    # ------------------------------------------------------------------
    gate5_pass = (
        live_bridge_observed
        and close_request_succeeded
        and app_exited_before_fallback
        and owned_runtime_count == 0
        and lock_pass
    )

    log("", out_lines)
    log("=" * 70, out_lines)
    log(f"  live_bridge_observed       = {live_bridge_observed}", out_lines)
    log(f"  live_bridge_python_paths   = {live_python_paths}", out_lines)
    log(f"  close_request_succeeded    = {close_request_succeeded}", out_lines)
    log(f"  app_exited_before_fallback = {app_exited_before_fallback}", out_lines)
    log(f"  owned_runtime_count        = {owned_runtime_count}", out_lines)
    log(f"  app_lockprobe_pass         = {lock_pass}", out_lines)
    log(f"  gate5_normal_close_pass    = {gate5_pass}", out_lines)
    log("=" * 70, out_lines)

    # ------------------------------------------------------------------
    # Step 10: Emergency cleanup ONLY after gate has been recorded
    # ------------------------------------------------------------------
    if not gate5_pass:
        log("Gate 5 FAIL recorded. Beginning emergency cleanup (will NOT convert to PASS).", out_lines)
        _emergency_cleanup(proc, pid, install_root, out_lines)
    else:
        log("Gate 5 PASS. No emergency cleanup needed.", out_lines)

    # ------------------------------------------------------------------
    # Output result
    # ------------------------------------------------------------------
    evidence = {
        "gate5_normal_close_pass": gate5_pass,
        "live_bridge_observed": live_bridge_observed,
        "live_bridge_python_paths": live_python_paths,
        "close_request_succeeded": close_request_succeeded,
        "app_exited_before_fallback": app_exited_before_fallback,
        "exit_elapsed_s": exit_elapsed_s,
        "close_timeout_s": args.timeout_s,
        "owned_runtime_count_post_close": owned_runtime_count,
        "app_lockprobe_pass": lock_pass,
        "app_lockprobe_detail": lock_detail,
        "fallback_invoked": not gate5_pass,
        "before_procs": before_procs,
        "pre_close_procs": pre_close_procs,
        "post_close_procs": post_close_procs,
    }
    _write_result(args.out, out_lines, gate5_pass, "normal_close_evaluated", evidence)
    return 0 if gate5_pass else 1


def _emergency_cleanup(proc: subprocess.Popen, pid: int, install_root: Path, out_lines: list[str]) -> None:
    """Force-kill after Gate 5 FAIL is already recorded. Must not change gate result."""
    try:
        if proc.poll() is None:
            log(f"EMERGENCY_CLEANUP: killing pid={pid}", out_lines)
            proc.kill()
            proc.wait(timeout=5)
    except Exception as exc:
        log(f"EMERGENCY_CLEANUP kill failed: {exc}", out_lines)

    # Also kill any owned runtime processes
    owned = find_owned_runtime_procs(install_root)
    for p in owned:
        try:
            subprocess.run(["taskkill", "/F", "/PID", str(p["Id"])],
                           capture_output=True, timeout=5)
            log(f"EMERGENCY_CLEANUP killed runtime pid={p['Id']}", out_lines)
        except Exception as exc:
            log(f"EMERGENCY_CLEANUP failed to kill pid={p['Id']}: {exc}", out_lines)


def _write_result(out_path, out_lines: list[str], gate_pass: bool, reason: str, evidence: dict) -> None:
    result = {
        "schema": "project-factory-gate5-lifecycle/1",
        "gate5_normal_close_pass": gate_pass,
        "reason": reason,
        "evidence": evidence,
        "raw_log": out_lines,
    }
    json_str = json.dumps(result, ensure_ascii=False, indent=2)
    print(json_str, flush=True)
    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(json_str, encoding="utf-8")
        print(f"Result written to: {out_path}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
