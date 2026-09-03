"""Clickable live-install helper: apply the newest kernel wheel, then start the GUI."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


def live_root() -> Path:
    local = os.environ.get("LOCALAPPDATA") or ""
    if not local:
        raise SystemExit("LOCALAPPDATA is missing.")
    root = Path(local) / "Programs" / "ProjectFactory"
    if not root.is_dir():
        raise SystemExit(f"Live install not found: {root}")
    return root


def wheel_version_key(path: Path) -> tuple[int, ...]:
    name = path.name
    prefix = "project_factory_blueprint_kernel-"
    if not name.startswith(prefix) or not name.endswith(".whl"):
        return (0,)
    mid = name[len(prefix) :].split("-py", 1)[0]
    parts: list[int] = []
    for item in mid.split("."):
        try:
            parts.append(int(item))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def newest_wheel(dirs: list[Path]) -> Path | None:
    found: list[Path] = []
    for directory in dirs:
        if directory.is_dir():
            found.extend(directory.glob("project_factory_blueprint_kernel-*.whl"))
    if not found:
        return None
    return max(found, key=wheel_version_key)


def search_dirs(script_dir: Path, live: Path) -> list[Path]:
    warehouse = Path(os.environ.get("LOCALAPPDATA") or "") / "ProjectFactory" / "warehouse" / "wheels"
    core_dist = script_dir.parent / "core" / "dist"
    return [
        script_dir / "wheel",
        core_dist,
        live / "wheel",
        warehouse,
    ]


def copy_backend(script_dir: Path, live: Path) -> list[str]:
    src = script_dir / "backend"
    if not src.is_dir():
        return []
    dest = live / "backend"
    dest.mkdir(parents=True, exist_ok=True)
    copied = []
    for path in sorted(src.glob("*.py")):
        target = dest / path.name
        if path.resolve() == target.resolve():
            continue
        shutil.copy2(path, target)
        copied.append(path.name)
    return copied


def copy_gui_overlay(script_dir: Path, live: Path) -> list[str]:
    candidates = []
    evidence = script_dir / "evidence"
    if evidence.is_dir():
        candidates.extend(sorted(evidence.glob("stage_*_live/gui_publish"), reverse=True))
    publish = script_dir / "gui_publish"
    if publish.is_dir():
        candidates.insert(0, publish)
    src = next((item for item in candidates if item.is_dir()), None)
    if src is None:
        return []
    dest = live / "app"
    copied = []
    for file in src.rglob("*"):
        if not file.is_file():
            continue
        target = dest / file.relative_to(src)
        if file.resolve() == target.resolve():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file, target)
        copied.append(str(file.relative_to(src)))
    return copied


def stop_gui() -> None:
    subprocess.run(
        ["taskkill", "/IM", "ProjectFactory.exe", "/F"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    time.sleep(1)


def apply_wheel(wheel: Path, live: Path) -> str:
    py = live / ".pf_runtime" / "Scripts" / "python.exe"
    if not py.is_file():
        raise SystemExit(f"live python missing: {py}")
    dest_dir = live / "wheel"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / wheel.name
    if wheel.resolve() != dest.resolve():
        shutil.copy2(wheel, dest)
    install = subprocess.run(
        [
            str(py),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-input",
            "--no-deps",
            "--force-reinstall",
            str(dest),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=180,
    )
    if install.returncode != 0:
        raise SystemExit(install.stdout + install.stderr)
    probe = subprocess.run(
        [str(py), "-c", "from project_factory.factory import FACTORY_VERSION; print(FACTORY_VERSION)"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=60,
    )
    return (probe.stdout or "").strip()


def launch_gui(live: Path) -> None:
    exe = live / "app" / "ProjectFactory.exe"
    if not exe.is_file():
        raise SystemExit(f"GUI missing: {exe}")
    os.startfile(str(exe))  # noqa: S606 - user launch entry


def main() -> int:
    parser = argparse.ArgumentParser(description="Project Factory live launch / hot-upgrade")
    parser.add_argument("--upgrade", action="store_true", help="Apply newest kernel wheel before launch")
    parser.add_argument("--wheel", help="Explicit .whl path")
    parser.add_argument("--no-launch", action="store_true", help="Do not start the GUI")
    args = parser.parse_args()

    live = live_root()
    script_dir = Path(__file__).resolve().parent
    print(f"live {live}")

    if args.upgrade:
        stop_gui()
        wheel = Path(args.wheel).expanduser() if args.wheel else newest_wheel(search_dirs(script_dir, live))
        if wheel is None or not Path(wheel).is_file():
            raise SystemExit("No kernel wheel found. Import one in 资源, or pass --wheel.")
        print(f"wheel {wheel}")
        version = apply_wheel(Path(wheel), live)
        print(f"kernel {version}")
        backend = copy_backend(script_dir, live)
        if backend:
            print("backend " + ", ".join(backend))
        gui = copy_gui_overlay(script_dir, live)
        if gui:
            print("gui " + ", ".join(gui))

    if not args.no_launch:
        launch_gui(live)
        print("launched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
