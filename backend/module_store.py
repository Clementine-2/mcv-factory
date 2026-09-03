"""Open-source functional modules. Not limited to Python .whl files."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from gui_catalog import OSS_MODULES


def _root() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "ProjectFactory"
    path = base / "warehouse" / "modules"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _index_file() -> Path:
    return _root() / "index.json"


def load_index() -> dict[str, Any]:
    path = _index_file()
    if not path.is_file():
        return {"schema": "project-factory-modules/1", "items": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_index(doc: dict[str, Any]) -> dict[str, Any]:
    path = _index_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return doc


def _family(item: dict[str, Any]) -> str:
    return str(item.get("family") or item.get("id") or item.get("label") or "other")


def _version_of(item: dict[str, Any]) -> str:
    return str(item.get("version") or ("preloaded" if item.get("status") == "preloaded" else "catalog"))


def _group_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for item in items:
        fam = _family(item)
        bucket = groups.setdefault(
            fam,
            {
                "id": fam,
                "label": item.get("label") or fam,
                "kind": item.get("kind") or "",
                "group": item.get("group") or "",
                "purpose": item.get("purpose") or "",
                "versions": [],
            },
        )
        version = {**item, "family": fam, "version": _version_of(item)}
        bucket["versions"].append(version)
    return list(groups.values())


def list_modules() -> dict[str, Any]:
    owned = {str(item.get("id")) + "@" + _version_of(item): item for item in load_index().get("items") or [] if isinstance(item, dict)}
    rows = []
    for spec in OSS_MODULES:
        key = spec["id"] + "@" + _version_of(spec)
        current = next((item for item in owned.values() if _family(item) == spec["id"]), {})
        rows.append(
            {
                **spec,
                "family": spec["id"],
                "version": spec.get("version") or "catalog",
                "status": current.get("status") or "catalog",
                "local_path": current.get("path") or "",
                "bytes": current.get("bytes") or 0,
            }
        )
    for item in owned.values():
        fam = _family(item)
        if not any(row.get("family") == fam and row.get("version") == _version_of(item) for row in rows):
            rows.append({**item, "family": fam, "group": item.get("group") or "用户导入", "version": _version_of(item)})
    return {"status": "OK", "directory": str(_root()), "items": rows, "groups": _group_items(rows)}


def download_module(module_id: str = "", url: str = "") -> dict[str, Any]:
    spec = next((item for item in OSS_MODULES if item["id"] == module_id), None)
    target = url or (spec or {}).get("url") or ""
    if not str(target).startswith(("http://", "https://")):
        raise ValueError("download needs a catalog id or http(s) url")
    name = module_id or str(target).rstrip("/").rsplit("/", 1)[-1] or "module"
    dest = _root() / name
    dest.mkdir(parents=True, exist_ok=True)
    snapshot = dest / "snapshot.json"
    with urlopen(target, timeout=60) as response:  # noqa: S310
        data = response.read(8 * 1024 * 1024 + 1)
    if len(data) > 8 * 1024 * 1024:
        raise ValueError("module metadata exceeds 8 MiB safety limit")
    snapshot.write_bytes(data)
    version = "preloaded"
    try:
        payload = json.loads(data.decode("utf-8", errors="replace"))
        if isinstance(payload, dict):
            version = str((payload.get("info") or {}).get("version") or payload.get("version") or (payload.get("dist-tags") or {}).get("latest") or "preloaded")
    except json.JSONDecodeError:
        version = "preloaded"
    record = {
        "id": name,
        "family": (spec or {}).get("id") or name,
        "version": version,
        "kind": (spec or {}).get("kind") or "url",
        "group": (spec or {}).get("group") or "下载",
        "label": (spec or {}).get("label") or name,
        "purpose": (spec or {}).get("purpose") or "用户下载的开源模块元数据",
        "source": (spec or {}).get("source") or target,
        "url": target,
        "path": str(snapshot),
        "bytes": len(data),
        "status": "preloaded",
    }
    doc = load_index()
    items = [item for item in doc.get("items") or [] if not (item.get("family") == record["family"] and item.get("version") == version)]
    items.append(record)
    doc["items"] = items
    save_index(doc)
    return {"status": "OK", "item": record, "note": "预载的是模块清单/元数据，不是把别人的源码偷偷收编成工厂产线。"}


def import_module(path: str) -> dict[str, Any]:
    src = Path(path).expanduser()
    if not src.is_file():
        raise ValueError(f"file not found: {src}")
    dest = _root() / src.name
    shutil.copy2(src, dest)
    record = {
        "id": src.stem,
        "family": src.stem,
        "version": "imported",
        "kind": src.suffix.lower().lstrip(".") or "file",
        "group": "用户导入",
        "label": src.name,
        "purpose": "用户放入仓库的开源功能模块",
        "source": str(src),
        "path": str(dest),
        "bytes": dest.stat().st_size,
        "status": "preloaded",
    }
    doc = load_index()
    items = [item for item in doc.get("items") or [] if not (item.get("family") == record["family"] and item.get("version") == record["version"])]
    items.append(record)
    doc["items"] = items
    save_index(doc)
    return {"status": "OK", "item": record}


def update_module(family: str, version: str, fields: dict[str, Any]) -> dict[str, Any]:
    doc = load_index()
    items = list(doc.get("items") or [])
    found = None
    for item in items:
        if _family(item) == family and _version_of(item) == version:
            for key in ("label", "purpose", "group", "url", "kind"):
                if key in fields and fields[key] is not None:
                    item[key] = fields[key]
            found = item
            break
    if found is None:
        raise ValueError("没有这条资源版本，目录项不能改成工厂产线。")
    doc["items"] = items
    save_index(doc)
    return {"status": "OK", "item": found}


def delete_module(family: str, version: str = "") -> dict[str, Any]:
    doc = load_index()
    kept = []
    removed = []
    for item in doc.get("items") or []:
        if _family(item) != family:
            kept.append(item)
            continue
        if version and _version_of(item) != version:
            kept.append(item)
            continue
        removed.append(item)
        path = Path(str(item.get("path") or ""))
        if path.is_file():
            path.unlink(missing_ok=True)
    if not removed:
        raise ValueError("目录里的工厂内置项不能删。只能删你预载/导入的版本。")
    doc["items"] = kept
    save_index(doc)
    return {"status": "OK", "removed": len(removed)}
