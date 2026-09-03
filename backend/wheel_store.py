"""User-managed Factory wheel/resource store. Auto-update is off unless opted in."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any
from urllib.request import urlopen

SCHEMA = "project-factory-wheel-store/1"


def _root() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "ProjectFactory"
    return base / "warehouse"


def store_file() -> Path:
    return _root() / "store.json"


def wheels_dir() -> Path:
    return _root() / "wheels"


def load_store() -> dict[str, Any]:
    path = store_file()
    if not path.is_file():
        return {
            "schema": SCHEMA,
            "auto_update": False,
            "store_dir": str(wheels_dir()),
            "items": [],
        }
    return json.loads(path.read_text(encoding="utf-8"))


def save_store(doc: dict[str, Any]) -> dict[str, Any]:
    path = store_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    wheels_dir().mkdir(parents=True, exist_ok=True)
    doc["schema"] = SCHEMA
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return doc


def list_store() -> dict[str, Any]:
    doc = load_store()
    live = Path(os.environ.get("LOCALAPPDATA") or "") / "Programs" / "ProjectFactory" / "wheel"
    live_items = []
    if live.is_dir():
        for path in sorted(live.glob("*.whl")):
            live_items.append({"name": path.name, "path": str(path), "source": "live-install"})
    return {"status": "OK", "store": doc, "live_wheels": live_items}


def set_auto_update(enabled: bool) -> dict[str, Any]:
    doc = load_store()
    doc["auto_update"] = bool(enabled)
    save_store(doc)
    return {"status": "OK", "auto_update": doc["auto_update"], "note": "observed_latest is never auto-promoted to supported."}


def import_local(path: str) -> dict[str, Any]:
    src = Path(path).expanduser()
    if not src.is_file():
        raise ValueError(f"file not found: {src}")
    dest_dir = wheels_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    shutil.copy2(src, dest)
    digest = hashlib.sha256(dest.read_bytes()).hexdigest()
    doc = load_store()
    items = list(doc.get("items") or [])
    items = [item for item in items if item.get("name") != dest.name]
    items.append({"name": dest.name, "path": str(dest), "sha256": digest, "source": "user-import"})
    doc["items"] = items
    save_store(doc)
    return {"status": "OK", "item": items[-1]}


def delete_wheel(path: str) -> dict[str, Any]:
    src = Path(path).expanduser()
    root = wheels_dir().resolve()
    resolved = src.resolve()
    if root not in resolved.parents and resolved.parent != root:
        raise ValueError("只能删除仓库里的 wheel，不能删安装目录里的机床包。")
    doc = load_store()
    doc["items"] = [item for item in doc.get("items") or [] if str(item.get("path")) != str(src) and str(item.get("path")) != str(resolved)]
    save_store(doc)
    if resolved.is_file():
        resolved.unlink()
    return {"status": "OK", "path": str(resolved)}


def download(url: str) -> dict[str, Any]:
    if not str(url).startswith(("http://", "https://")):
        raise ValueError("url must be http(s)")
    dest_dir = wheels_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = url.rstrip("/").rsplit("/", 1)[-1] or "download.bin"
    dest = dest_dir / name
    with urlopen(url, timeout=120) as response:  # noqa: S310 - user initiated
        data = response.read(64 * 1024 * 1024 + 1)
    if len(data) > 64 * 1024 * 1024:
        raise ValueError("download exceeds 64 MiB safety limit")
    dest.write_bytes(data)
    digest = hashlib.sha256(dest.read_bytes()).hexdigest()
    doc = load_store()
    items = list(doc.get("items") or [])
    items = [item for item in items if item.get("name") != dest.name]
    items.append({"name": dest.name, "path": str(dest), "sha256": digest, "source": "user-download", "url": url})
    doc["items"] = items
    save_store(doc)
    return {"status": "OK", "item": items[-1]}


def apply_kernel_wheel(path: str) -> dict[str, Any]:
    """Hot-upgrade the live Factory kernel. User initiated. Does not rebuild Setup.exe."""
    import subprocess

    src = Path(path).expanduser()
    if not src.is_file() or src.suffix.lower() != ".whl":
        raise ValueError("apply requires a .whl file")
    live = Path(os.environ.get("LOCALAPPDATA") or "") / "Programs" / "ProjectFactory"
    py = live / ".pf_runtime" / "Scripts" / "python.exe"
    if not py.is_file():
        raise ValueError(f"live python missing: {py}")
    dest_dir = live / "wheel"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    shutil.copy2(src, dest)
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
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=120,
        check=False,
    )
    if install.returncode != 0:
        raise RuntimeError(install.stdout + install.stderr)
    probe = subprocess.run(
        [str(py), "-c", "from project_factory.factory import FACTORY_VERSION; print(FACTORY_VERSION)"],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=60,
        check=False,
    )
    version = (probe.stdout or "").strip()
    doc = load_store()
    doc["active_kernel"] = {"path": str(dest), "version": version, "name": dest.name}
    save_store(doc)
    return {
        "status": "OK",
        "version": version,
        "path": str(dest),
        "note": "Kernel hot-upgraded. Use 启动工厂.bat if the window should be restarted.",
    }
