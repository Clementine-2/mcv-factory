"""User-imported Factory resources. Stored locally; not auto-owned production lines."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

import yaml


def resources_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "ProjectFactory"
    path = base / "user_warehouse"
    path.mkdir(parents=True, exist_ok=True)
    return path


def list_resources() -> dict[str, Any]:
    items = []
    root = resources_dir()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            items.append({"name": str(path.relative_to(root)).replace("\\", "/"), "path": str(path), "bytes": path.stat().st_size})
    return {"status": "OK", "directory": str(root), "items": items}


def import_resource(path: str) -> dict[str, Any]:
    src = Path(path).expanduser()
    if not src.is_file():
        raise ValueError(f"file not found: {src}")
    dest = resources_dir() / src.name
    shutil.copy2(src, dest)
    kind = "yaml" if dest.suffix.lower() in {".yaml", ".yml"} else dest.suffix.lower().lstrip(".")
    preview = None
    if kind == "yaml":
        try:
            preview = yaml.safe_load(dest.read_text(encoding="utf-8"))
            if isinstance(preview, dict):
                preview = {key: preview[key] for key in list(preview)[:8]}
        except (OSError, yaml.YAMLError):
            preview = None
    return {"status": "OK", "item": {"name": dest.name, "path": str(dest), "kind": kind, "preview": preview}, "note": "Imported as observed user resource. It does not become an owned production line until a Factory plugin owns it."}


def delete_resource(path: str) -> dict[str, Any]:
    src = Path(path).expanduser()
    root = resources_dir().resolve()
    resolved = src.resolve()
    if root not in resolved.parents and resolved.parent != root:
        raise ValueError("can only delete files inside the user warehouse")
    if not resolved.is_file():
        raise ValueError("file not found")
    resolved.unlink()
    return {"status": "OK", "path": str(resolved)}


def export_blueprint(spec: dict[str, Any], dest: str) -> dict[str, Any]:
    path = Path(dest).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".json":
        path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        path.write_text(yaml.safe_dump(spec, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return {"status": "OK", "path": str(path)}


def load_blueprint(path: str) -> dict[str, Any]:
    src = Path(path).expanduser()
    text = src.read_text(encoding="utf-8")
    if src.suffix.lower() == ".json":
        payload = json.loads(text)
    else:
        payload = yaml.safe_load(text)
    if not isinstance(payload, dict):
        raise ValueError("blueprint file must be an object")
    return {"status": "OK", "spec": payload}
