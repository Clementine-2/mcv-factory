from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import traceback
import venv

ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / ".pf_runtime"
APPDATA_ROOT = (Path(os.environ["LOCALAPPDATA"]) / "ProjectFactory") if os.name == "nt" and os.environ.get("LOCALAPPDATA") else Path.home() / ".project-factory"
LOG_DIR = APPDATA_ROOT / "logs"
LOG_PATH = LOG_DIR / "bootstrap.log"
MARKER = RUNTIME / ".project_factory_install.json"
WHEEL = ROOT / "wheel" / "project_factory_blueprint_kernel-0.14.30-py3-none-any.whl"
MIN_PYTHON = (3, 11)
BOOTSTRAP_SCHEMA = "ux5-runtime-1"
FACTORY_VERSION = "0.14.30"

sys.path.insert(0, str(ROOT / "backend"))
from network_ops import AUTO_SOURCE_NAME, SOURCE_OPTIONS, source_failover_order, record_source_success, self_test as network_self_test

PINNED = (
    "attrs==26.1.0",
    "jsonschema-specifications==2025.9.1",
    "referencing==0.37.0",
    "rpds-py==2026.5.1",
    "typing-extensions==4.16.0",
    "jsonschema==4.26.0",
    "PyYAML==6.0.3",
    "uv==0.10.0",
)
EXPECTED = {
    "project-factory-blueprint-kernel": FACTORY_VERSION,
    "attrs": "26.1.0",
    "jsonschema-specifications": "2025.9.1",
    "referencing": "0.37.0",
    "rpds-py": "2026.5.1",
    "typing-extensions": "4.16.0",
    "jsonschema": "4.26.0",
    "PyYAML": "6.0.3",
    "uv": "0.10.0",
}


def log(message: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    line = str(message)
    print(line, flush=True)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def runtime_bin_dir() -> Path:
    return RUNTIME / ("Scripts" if os.name == "nt" else "bin")


def runtime_python() -> Path:
    return RUNTIME / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def clean_env(*, connection: str = "current", custom_proxy: str = "") -> dict[str, str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env["PYTHONUTF8"] = "1"
    for key in list(env):
        if key.upper().startswith("PIP_"):
            env.pop(key, None)
    if connection in {"direct", "custom"}:
        for key in list(env):
            if "PROXY" in key.upper():
                env.pop(key, None)
    if connection == "direct":
        env["NO_PROXY"] = "*"
        env["no_proxy"] = "*"
    elif connection == "custom":
        proxy = custom_proxy.strip()
        if not proxy:
            raise ValueError("自定义代理模式需要代理地址。")
        env["HTTP_PROXY"] = proxy
        env["HTTPS_PROXY"] = proxy
        env["http_proxy"] = proxy
        env["https_proxy"] = proxy
    current = env.get("PATH", "")
    env["PATH"] = str(runtime_bin_dir()) + (os.pathsep + current if current else "")
    return env


def _uv_version(py: Path) -> tuple[str, str]:
    uv = py.parent / ("uv.exe" if os.name == "nt" else "uv")
    if not uv.is_file():
        return "", f"uv executable missing: {uv}"
    try:
        p = subprocess.run([str(uv), "--version"], cwd=ROOT, env=clean_env(), text=True, encoding="utf-8", errors="replace",
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=20, check=False)
        if p.returncode != 0:
            return "", f"uv --version exit={p.returncode}: {p.stdout.strip()}"
        match = re.search(r"\b(\d+\.\d+\.\d+)\b", p.stdout)
        return (match.group(1), "") if match else ("", f"unrecognized uv --version output: {p.stdout.strip()}")
    except Exception as exc:
        return "", f"uv probe failed: {type(exc).__name__}: {exc}"


def installed_state(py: Path) -> dict[str, object]:
    names = [name for name in EXPECTED if name != "uv"]
    code = """
import importlib.metadata as m, json
names = %r
versions, errors = {}, {}
for name in names:
    try: versions[name] = m.version(name)
    except Exception as exc: errors[name] = type(exc).__name__ + ': ' + str(exc)
print(json.dumps({'versions': versions, 'errors': errors}))
""" % names
    state: dict[str, object] = {"versions": {}, "errors": {}}
    try:
        p = subprocess.run([str(py), "-c", code], cwd=ROOT, env=clean_env(), text=True, encoding="utf-8", errors="replace",
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=25, check=False)
        if p.returncode != 0:
            state["probe_error"] = f"metadata probe exit={p.returncode}: {p.stdout.strip()}"
        else:
            payload = json.loads(p.stdout.strip().splitlines()[-1])
            state["versions"] = payload.get("versions", {})
            state["errors"] = payload.get("errors", {})
    except Exception as exc:
        state["probe_error"] = f"metadata probe failed: {type(exc).__name__}: {exc}"
    uv_version, uv_error = _uv_version(py)
    versions = dict(state.get("versions") or {})
    versions["uv"] = uv_version
    state["versions"] = versions
    if uv_error:
        errors = dict(state.get("errors") or {})
        errors["uv"] = uv_error
        state["errors"] = errors
    return state


def runtime_mismatches(state: dict[str, object]) -> list[str]:
    versions = dict(state.get("versions") or {})
    mismatches = [f"{name}: expected {wanted}, got {versions.get(name) or '<missing>'}" for name, wanted in EXPECTED.items() if versions.get(name) != wanted]
    if state.get("probe_error"):
        mismatches.append(str(state["probe_error"]))
    errors = dict(state.get("errors") or {})
    for name, error in errors.items():
        if not versions.get(name):
            mismatches.append(f"{name}: {error}")
    return mismatches


def ready(wheel_hash: str) -> bool:
    py = runtime_python()
    if not py.is_file() or not MARKER.is_file():
        return False
    try:
        marker = json.loads(MARKER.read_text(encoding="utf-8"))
    except Exception:
        return False
    if marker.get("bootstrap_schema") != BOOTSTRAP_SCHEMA or marker.get("wheel_sha256") != wheel_hash:
        return False
    return not runtime_mismatches(installed_state(py))


def _factory_installed(py: Path) -> bool:
    return dict(installed_state(py).get("versions") or {}).get("project-factory-blueprint-kernel") == FACTORY_VERSION


def _install_with_failover(py: Path, *, source_name: str, connection_name: str, custom_proxy: str, on_line) -> str:
    mode = {"强制直连（忽略代理）": "direct", "当前系统/代理配置": "current", "自定义代理": "custom"}.get(connection_name, "direct")
    sources = source_failover_order(source_name)
    last_error: BaseException | None = None
    for number, source in enumerate(sources, start=1):
        index_url = SOURCE_OPTIONS[source]
        on_line(f"[SOURCE {number}/{len(sources)}] {source} -> {index_url}")
        cmd = [str(py), "-m", "pip", "install", "--disable-pip-version-check", "--no-input", "--only-binary=:all:",
               "--progress-bar", "on", "--timeout", "15", "--retries", "0", "--isolated", "--index-url", index_url, "--upgrade", *PINNED]
        try:
            _stream(cmd, env=clean_env(connection=mode, custom_proxy=custom_proxy), on_line=on_line, timeout=240)
            on_line(f"[SOURCE-OK] {source}")
            record_source_success(source)
            return source
        except BaseException as exc:
            last_error = exc
            on_line(f"[SOURCE-FAILED] {source}: {type(exc).__name__}: {exc}")
            if number < len(sources):
                on_line("[AUTO-RETRY] 自动切换下一镜像源；已完成的 pip 缓存继续复用。")
    raise RuntimeError(f"镜像池全部失败。最后错误: {last_error}")


def ensure_runtime(on_line=log, *, source_name: str = AUTO_SOURCE_NAME, connection_name: str = "强制直连（忽略代理）", custom_proxy: str = "") -> Path:
    wheel_hash = sha256(WHEEL)
    py = runtime_python()
    if ready(wheel_hash):
        on_line("[OK] UX5.0 private Python core runtime already ready.")
        return py
    if not py.is_file():
        on_line("[SETUP 1/3] Creating isolated Python core runtime (.pf_runtime).")
        venv.EnvBuilder(with_pip=True, clear=False).create(RUNTIME)
        py = runtime_python()
    if _factory_installed(py):
        on_line("[SETUP 2/3] Bundled Factory 0.14.30 wheel already installed; skipping reinstall.")
    else:
        on_line("[SETUP 2/3] Installing bundled Factory 0.14.30 wheel locally (no network).")
        _stream([str(py), "-m", "pip", "install", "--disable-pip-version-check", "--no-input", "--no-deps", "--force-reinstall", str(WHEEL)],
                env=clean_env(), on_line=on_line, timeout=120)
    on_line(f"[SETUP 3/3] Preparing pinned Python Core dependencies via {source_name} / {connection_name}.")
    on_line("[POLICY] WPF/.NET owns the GUI. Python runtime contains Core dependencies only; system Python is not modified.")
    successful_source = _install_with_failover(py, source_name=source_name, connection_name=connection_name, custom_proxy=custom_proxy, on_line=on_line)
    state = installed_state(py)
    on_line("[VERIFY] Runtime state: " + json.dumps(state, ensure_ascii=False, sort_keys=True))
    mismatches = runtime_mismatches(state)
    if mismatches:
        on_line("[VERIFY-FAILED] Package installation completed, but runtime verification failed. Source switching will not be retried because this is not a network failure.")
        for item in mismatches:
            on_line("  - " + item)
        raise RuntimeError("Runtime verification failed: " + "; ".join(mismatches))
    MARKER.write_text(json.dumps({"bootstrap_schema": BOOTSTRAP_SCHEMA, "wheel_sha256": wheel_hash, "factory_version": FACTORY_VERSION,
                                  "successful_source": successful_source, "network_default": f"{source_name}|{connection_name}", "state": state},
                                 ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    on_line(f"[OK] UX5.1 Python Core runtime verified via {successful_source}: Factory 0.14.30 / uv 0.10.0.")
    return py


def _stream(cmd: list[str], *, env: dict[str, str], on_line, timeout: int) -> None:
    on_line("[RUN] " + subprocess.list2cmdline(cmd))
    p = subprocess.Popen(cmd, cwd=ROOT, env=env, text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    lines: queue.Queue[str | None] = queue.Queue()
    def reader() -> None:
        assert p.stdout is not None
        for line in p.stdout:
            lines.put(line.rstrip())
        lines.put(None)
    threading.Thread(target=reader, daemon=True).start()
    monotonic = __import__("time").monotonic
    deadline = monotonic() + timeout
    ended = False
    while not ended:
        if monotonic() > deadline:
            p.kill()
            raise RuntimeError(f"Setup command exceeded {timeout}s hard timeout.")
        try:
            item = lines.get(timeout=0.1)
        except queue.Empty:
            continue
        if item is None:
            ended = True
        elif item:
            on_line(item)
    rc = p.wait(timeout=10)
    if rc != 0:
        raise RuntimeError(f"Setup command failed with exit code {rc}.")


def _source_label(value: str) -> str:
    return {"auto": AUTO_SOURCE_NAME, "tuna": "清华 TUNA", "bfsu": "北外 BFSU", "ustc": "中科大 USTC", "aliyun": "阿里云", "huawei": "华为云", "pypi": "官方 PyPI"}[value]


def _connection_label(value: str) -> str:
    return {"direct": "强制直连（忽略代理）", "current": "当前系统/代理配置", "custom": "自定义代理"}[value]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--source", choices=("auto", "tuna", "bfsu", "ustc", "aliyun", "huawei", "pypi"), default="auto")
    parser.add_argument("--connection", choices=("direct", "current", "custom"), default="direct")
    parser.add_argument("--custom-proxy", default="")
    args = parser.parse_args(argv)

    log("=" * 72)
    log("Project Factory Windows Fluent bootstrap UX5.0")
    log(f"Launcher Python: {sys.version.split()[0]} ({sys.executable})")
    if sys.version_info < MIN_PYTHON:
        log("[BLOCKED] Python 3.11+ required.")
        return 4
    if not WHEEL.is_file():
        log("[BLOCKED] Bundled Factory wheel missing.")
        return 4
    if args.self_test:
        assert BOOTSTRAP_SCHEMA == "ux5-runtime-1"
        assert "ttkbootstrap" not in " ".join(PINNED)
        assert "Pillow" not in " ".join(PINNED)
        assert PINNED[-1] == "uv==0.10.0"
        network_self_test()
        log("[OK] UX5 bootstrap static self-test passed; no Tk GUI dependency remains.")
        return 0

    if args.verify_only:
        state = installed_state(runtime_python()) if runtime_python().is_file() else {"versions": {}, "errors": {"python": "missing"}}
        log("[VERIFY] " + json.dumps(state, ensure_ascii=False, sort_keys=True))
        mismatches = runtime_mismatches(state)
        if mismatches:
            for item in mismatches:
                log("  - " + item)
            return 4
        log("[OK] Private Python Core runtime verified.")
        return 0

    if not args.prepare_only:
        log("[BLOCKED] UX5 bootstrap is installer/recovery infrastructure only. Use ProjectFactory.exe for the GUI.")
        return 4

    try:
        source_name = _source_label(args.source)
        connection_name = _connection_label(args.connection)
        custom_proxy = args.custom_proxy.strip() or os.environ.get("PROJECT_FACTORY_SETUP_PROXY", "").strip()
        ensure_runtime(source_name=source_name, connection_name=connection_name, custom_proxy=custom_proxy)
        log("[OK] PREPARE_ONLY complete; Python Core runtime is verified.")
        return 0
    except Exception as exc:
        log(f"[BLOCKED] {exc}")
        for line in traceback.format_exc().rstrip().splitlines():
            log("  " + line)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
