"""Factory tool lookup.

Owned tools (work/core/.tools, install dir) are PREPENDED to PATH so the factory
prefers its validated copy when present, but the system PATH is always used as a
fallback — the developer's own environment is never modified. As of T23 the version
gate is removed: any detected tool version is accepted (status reported, not blocked),
so developers can use and manage their own toolchain freely.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def owned_tool_roots() -> list[Path]:
    roots: list[Path] = []
    extra = os.environ.get("PROJECT_FACTORY_TOOLS", "").strip()
    if extra:
        roots.append(Path(extra))
    local = os.environ.get("LOCALAPPDATA") or ""
    if local:
        roots.append(Path(local) / "ProjectFactory" / "tools")
        roots.append(Path(local) / "Programs" / "ProjectFactory" / "tools")
    core_tools = Path(__file__).resolve().parents[2] / ".tools"
    if core_tools.is_dir():
        roots.append(core_tools)
    seen: set[str] = set()
    unique: list[Path] = []
    for root in roots:
        key = str(root)
        if key in seen:
            continue
        seen.add(key)
        unique.append(root)
    return unique


def owned_provider_dirs() -> list[Path]:
    dirs: list[Path] = []
    for root in owned_tool_roots():
        dirs.extend(
            (
                root / "uv010" / "bin",
                root / "npm1092",
                root / "npm1092" / "package" / "bin",
                root / "maturin_py" / "bin",
            )
        )
    return [path for path in dirs if path.is_dir()]


def apply_owned_tools_path() -> list[str]:
    prepend = [str(path) for path in owned_provider_dirs()]
    if not prepend:
        return []
    current = os.environ.get("PATH", "")
    parts = [item for item in current.split(os.pathsep) if item]
    lowered = {item.casefold() for item in parts}
    new = [item for item in prepend if item.casefold() not in lowered]
    os.environ["PATH"] = os.pathsep.join(new + parts)
    return new


def resolve_executable(name: str) -> str | None:
    apply_owned_tools_path()
    names = [name, f"{name}.cmd", f"{name}.exe", f"{name}.bat"] if os.name == "nt" else [name]
    for directory in owned_provider_dirs():
        for candidate in names:
            path = directory / candidate
            if path.is_file():
                return str(path)
    return shutil.which(name)
