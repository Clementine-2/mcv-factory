"""Shared pytest fixtures for the Factory Core test suite.

Materializes the legacy (lock schema 0.5) upgrade fixture under
``core/history/p7_golden_outputs/`` by downgrading the committed golden output.
``history/`` is intentionally gitignored: the fixture is *derived data*, rebuilt
from the committed golden on every test session. The legacy fixture records the
live scaffolding-provider (uv) version at build time so the migration tests run
on any machine — local or CI — that has uv installed. On machines without uv the
fixture is not built and the legacy upgrade tests skip themselves.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_SOURCE = ROOT / "golden_outputs" / "json-batch-cli.zip"
P7_GOLDEN = ROOT / "history" / "p7_golden_outputs" / "json-batch-cli.zip"

LEGACY_LOCK_SCHEMA = "0.5"
LEGACY_FACTORY = {"stage": "P7", "version": "0.8.0"}
UPGRADE_DISCIPLINE_MARKER = "## Factory upgrade discipline"


def live_scaffolding_version() -> str | None:
    """Detect the uv version the legacy fixture must record to test cleanly.

    Uses the registry's own provider probe (same mechanism as ``plan_upgrade``),
    so the recorded version always matches the runtime's reported version —
    including a Factory-owned pinned toolchain that shadows the PATH binary.
    """
    try:
        from project_factory.registry import inspect_provider, load_registry

        return inspect_provider(load_registry().providers["uv"]).version
    except Exception:
        return None


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _strip_upgrade_discipline(text: str) -> str:
    """Remove the upgrade-discipline section so the migration re-appends it."""
    if UPGRADE_DISCIPLINE_MARKER not in text:
        return text
    return text.split(UPGRADE_DISCIPLINE_MARKER)[0].rstrip() + "\n"


def build_p7_golden(uv_version: str) -> None:
    """Build the legacy P7 project zip from the committed golden output."""
    P7_GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    work = P7_GOLDEN.parent / "json-batch-cli"
    if work.exists():
        shutil.rmtree(work)

    with zipfile.ZipFile(GOLDEN_SOURCE) as archive:
        archive.extractall(P7_GOLDEN.parent)

    # 1) Downgrade the project lock to a legacy (0.5) shape.
    lock_path = work / "project.lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    lock["lock_schema_version"] = LEGACY_LOCK_SCHEMA
    lock["factory"] = dict(LEGACY_FACTORY)
    lock["host_integration"] = None
    lock["runner_integration"] = None
    lock["extensions"] = []
    for key in ("upgrade_contract", "upgrade_history", "verification", "extension_contract", "extension_artifacts"):
        lock.pop(key, None)
    lock["providers"] = {
        "project_scaffolding": {
            "id": "uv",
            "version": uv_version,
            "capability": "project_scaffolding",
            "integration": "public-cli",
            "upstream_source_modified": False,
            "compatibility_state": "SUPPORTED",
        }
    }

    # 2) generation.json must not pretend the upgrade contract already ran.
    generation_path = work / ".project/generation.json"
    generation = json.loads(generation_path.read_text(encoding="utf-8"))
    generation.pop("factory_upgrade_contract", None)
    generation_path.write_text(
        json.dumps(generation, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    # 3) Strip the upgrade-discipline section so plan/apply re-append it.
    for relative in (".project/contract/agent-contract.md", "AGENTS.md", "CLAUDE.md"):
        path = work / relative
        path.write_text(_strip_upgrade_discipline(path.read_text(encoding="utf-8")), encoding="utf-8")

    # 4) The migration must not ship extension receipts (legacy project has none).
    extensions_lock = work / ".project/extensions.lock.json"
    extensions_lock.unlink(missing_ok=True)

    # 5) Recompute managed-file preimages over the transformed tree.
    managed = lock.get("managed_files", {})
    lock["managed_files"] = {
        relative: {"ownership": "factory-managed", "sha256": _sha256_bytes((work / relative).read_bytes())}
        for relative in managed
        if (work / relative).is_file()
    }
    lock_path.write_text(
        json.dumps(lock, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with zipfile.ZipFile(P7_GOLDEN, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(work.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(P7_GOLDEN.parent).as_posix())

    shutil.rmtree(work)


def pytest_sessionstart(session) -> None:
    """Build the legacy fixture once per session when a provider is available."""
    del session  # unused
    uv_version = live_scaffolding_version()
    if uv_version and GOLDEN_SOURCE.is_file():
        build_p7_golden(uv_version)