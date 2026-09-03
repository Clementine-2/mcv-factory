from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Iterable


BASE_FACTORY_MANAGED_PATHS = (
    ".project/contract/agent-contract.md",
    ".project/generation.json",
    ".project/evidence/harness-compatibility.json",
    ".project/extensions.lock.json",
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def managed_paths_from_lock(lock: dict[str, Any]) -> tuple[str, ...]:
    from .overlay import OVERLAY_MANAGED_PATHS

    paths: list[str] = list(BASE_FACTORY_MANAGED_PATHS)
    paths.extend(OVERLAY_MANAGED_PATHS)
    # B06/B01: per-profile skills are Factory-owned overlay; preserve under upgrades
    profile_id = str((lock.get("profile") or {}).get("id", "")).strip()
    if profile_id and profile_id != "blank":
        paths.append(f"skills/{profile_id}/SKILL.md")
    assembly = lock.get("assembly") or {}
    for pkg in assembly.get("packages") or []:
        pid = str(pkg.get("profile", "")).strip()
        if pid:
            paths.append(f"skills/{pid}/SKILL.md")
    harness = lock.get("harness_contract", {})
    for adapter in harness.get("adapters", {}).values():
        context_file = str(adapter.get("context_file", "")).strip()
        if context_file:
            paths.append(context_file)
    for artifact in lock.get("extension_artifacts", []):
        relative = str(artifact.get("path", "")).strip()
        if relative:
            paths.append(relative)
    if lock.get("process_integration"):
        paths.extend(
            (
                ".project/evidence/process-integration.json",
                ".project/process/spec-kit-plan.json",
                ".project/process/INSTALL.md",
            )
        )
    host = lock.get("host_integration")
    if isinstance(host, dict) and host.get("hosts"):
        paths.extend((".project/evidence/host-compatibility.json", ".project/host/README.md"))
        for item in host.get("hosts", {}).values():
            relative = str(item.get("plan_path", "")).strip()
            if relative:
                paths.append(relative)
    runner = lock.get("runner_integration")
    if isinstance(runner, dict):
        paths.extend((
            ".project/evidence/runner-compatibility.json",
            ".project/runner/CONTRACT.md",
            ".project/runner/README.md",
            ".project/runner/state/README.md",
        ))
        relative = str(runner.get("plan", {}).get("path", "")).strip()
        if relative:
            paths.append(relative)
    return tuple(dict.fromkeys(paths))


def collect_managed_file_hashes(project_root: Path, paths: Iterable[str]) -> dict[str, dict[str, str]]:
    root = Path(project_root)
    result: dict[str, dict[str, str]] = {}
    for relative in paths:
        path = root / relative
        if path.is_file():
            result[relative] = {"sha256": sha256_file(path), "ownership": "factory-managed"}
    return result

FACTORY_OVERLAY_MANIFEST_PATH = Path('.project/FACTORY_OVERLAY_MANIFEST.sha256')


def write_factory_overlay_manifest(project_root: Path, paths: Iterable[str]) -> Path:
    root = Path(project_root)
    manifest = root / FACTORY_OVERLAY_MANIFEST_PATH
    lines: list[str] = []
    for relative in sorted(dict.fromkeys(str(item) for item in paths)):
        path = root / relative
        if path.is_file() and relative != FACTORY_OVERLAY_MANIFEST_PATH.as_posix():
            lines.append(f"{sha256_file(path)}  {relative}")
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest


def verify_factory_overlay_manifest(project_root: Path) -> tuple[bool, list[str]]:
    root = Path(project_root)
    manifest = root / FACTORY_OVERLAY_MANIFEST_PATH
    if not manifest.is_file():
        return False, [f"{FACTORY_OVERLAY_MANIFEST_PATH.as_posix()} is missing"]
    failures: list[str] = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            expected, relative = line.split("  ", 1)
        except ValueError:
            failures.append(f"Malformed Factory overlay manifest line: {line}")
            continue
        rel = Path(relative)
        if not relative or "\\" in relative or rel.is_absolute() or ".." in rel.parts:
            failures.append(f"Unsafe Factory-owned path: {relative}")
            continue
        path = root / rel
        if not path.is_file():
            failures.append(f"Missing Factory-owned file: {relative}")
        elif sha256_file(path) != expected:
            failures.append(f"Factory-owned hash mismatch: {relative}")
    return not failures, failures
