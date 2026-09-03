from __future__ import annotations

import argparse
import hashlib
import difflib
import io
import json
import shutil
import tempfile
import zipfile
from types import SimpleNamespace
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .factory import FACTORY_STAGE, FACTORY_VERSION, FactoryError
from .extensions import (
    ExtensionError,
    ExtensionRuntime,
    assert_upgrade_extension_set,
    build_existing_extension_receipt,
    collect_extension_migration_targets,
    load_extension_runtime,
    verify_extension_receipt,
)
from .harness import CANONICAL_CONTRACT_PATH, verify_harness_contracts
from .host import HOST_EVIDENCE_PATH, HOST_README_PATH, verify_host_materialization
from .runner import verify_runner_materialization
from .ownership import (
    FACTORY_OVERLAY_MANIFEST_PATH,
    collect_managed_file_hashes,
    managed_paths_from_lock,
    sha256_file,
    verify_factory_overlay_manifest,
    write_factory_overlay_manifest,
)
from .overlay import OverlayError, render_overlay_targets
from .registry import RegistryError, inspect_provider, load_registry
from .verification import VerificationError, assert_required_gates, build_verification_suite, execute_verification_suite


class UpgradeError(RuntimeError):
    """Raised when an existing project cannot be safely upgraded."""


SUPPORTED_SOURCE_LOCKS = {"0.5", "0.6", "0.7", "0.8", "0.9"}
TARGET_LOCK_SCHEMA = "0.9"
UPGRADE_CONTRACT_VERSION = "0.3"
AGENT_CONTRACT_UPGRADE_MARKER = "## Factory upgrade discipline"


@dataclass(frozen=True)
class UpgradeChange:
    path: str
    action: str
    ownership: str
    current_sha256: str | None
    expected_prior_sha256: str | None
    proposed_sha256: str | None
    conflict: bool
    reason: str
    diff_preview: str | None = None


@dataclass(frozen=True)
class UpgradePlan:
    schema_version: str
    upgrade_id: str
    project_name: str
    source_factory_version: str
    source_factory_stage: str
    source_lock_schema: str
    target_factory_version: str
    target_factory_stage: str
    target_lock_schema: str
    migration_id: str
    status: str
    risk: str
    changes: tuple[UpgradeChange, ...]
    blocked_reasons: tuple[str, ...]
    verification: tuple[str, ...]
    rollback: dict[str, Any]
    plan_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise UpgradeError(f"Expected JSON object: {path}")
    return value


def _manifest_hashes(project_root: Path) -> dict[str, str]:
    manifest = project_root / "PROJECT_MANIFEST.sha256"
    if not manifest.is_file():
        raise UpgradeError("PROJECT_MANIFEST.sha256 is required for legacy ownership checks.")
    result: dict[str, str] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            digest, relative = line.split("  ", 1)
        except ValueError as exc:
            raise UpgradeError(f"Malformed manifest line: {line}") from exc
        result[relative] = digest
    return result


def _source_expected_hashes(project_root: Path, lock: dict[str, Any]) -> dict[str, str]:
    managed = lock.get("managed_files")
    if isinstance(managed, dict):
        out: dict[str, str] = {}
        for path, record in managed.items():
            if isinstance(record, dict) and record.get("sha256"):
                out[str(path)] = str(record["sha256"])
        if out:
            return out
    return _manifest_hashes(project_root)


def _portable_upgrade_id(
    project_name: str,
    source_manifest_sha: str,
    target_extension_versions: dict[str, str] | None = None,
) -> str:
    extension_fingerprint = json.dumps(target_extension_versions or {}, sort_keys=True, separators=(",", ":"))
    seed = f"{project_name}|{source_manifest_sha}|{FACTORY_VERSION}|{TARGET_LOCK_SCHEMA}|overlay-v3|{extension_fingerprint}"
    return "upgrade-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def _agent_contract_target(current: str) -> str:
    if AGENT_CONTRACT_UPGRADE_MARKER in current:
        return current
    suffix = '''\n## Factory upgrade discipline\n\n- Treat Factory upgrades as explicit migrations, never as automatic dependency refreshes.\n- Inspect the DryRun plan and rollback scope before applying Factory-owned overlay changes.\n- A Factory-owned file that diverged from its recorded preimage is a conflict; do not overwrite it silently.\n- Business/source files are outside the Factory overlay unless a future migration explicitly declares otherwise.\n'''
    return current.rstrip() + "\n" + suffix


def _harness_evidence_target(lock: dict[str, Any], contract_sha: str) -> dict[str, Any]:
    adapters: dict[str, Any] = {}
    claims: list[dict[str, Any]] = []
    for harness_id, prior in lock.get("harness_contract", {}).get("adapters", {}).items():
        context_file = str(prior.get("context_file", ""))
        adapter = dict(prior)
        adapter["contract_sha256"] = contract_sha
        adapter["context_sha256"] = contract_sha
        adapter["runtime_status"] = "UNVERIFIED_AFTER_UPGRADE"
        adapters[harness_id] = adapter
        claims.extend(
            (
                {
                    "id": f"{harness_id}-context-contract",
                    "scope": context_file,
                    "status": "VERIFIED",
                    "evidence": {
                        "canonical_path": CANONICAL_CONTRACT_PATH.as_posix(),
                        "canonical_sha256": contract_sha,
                        "context_sha256": contract_sha,
                    },
                    "limitation": "Only context-file parity is verified during the metadata upgrade.",
                },
                {
                    "id": f"{harness_id}-runtime",
                    "scope": str(prior.get("id", harness_id)),
                    "status": "UNVERIFIED",
                    "evidence": {"runtime_probe": "NOT_RUN_DURING_UPGRADE"},
                    "limitation": "Harness runtime execution is outside the upgrade verification scope.",
                },
            )
        )
    return {
        "schema_version": "0.1",
        "status": "PARTIALLY_VERIFIED",
        "canonical_contract": {"path": CANONICAL_CONTRACT_PATH.as_posix(), "sha256": contract_sha},
        "adapters": adapters,
        "claims": claims,
        "limitations": [
            "Context-file parity is re-verified by the upgrade; live harness execution is not performed.",
            "Runtime status is deliberately reset to UNVERIFIED_AFTER_UPGRADE rather than inherited as fresh evidence.",
        ],
    }


def _render_targets(project_root: Path, lock: dict[str, Any], upgrade_id: str) -> dict[str, bytes | None]:
    canonical_path = project_root / CANONICAL_CONTRACT_PATH
    if not canonical_path.is_file():
        raise UpgradeError("Canonical Agent Contract is missing.")
    current_text = canonical_path.read_text(encoding="utf-8")
    if AGENT_CONTRACT_UPGRADE_MARKER in current_text:
        contract_bytes = canonical_path.read_bytes()
    else:
        contract_bytes = _agent_contract_target(current_text).encode("utf-8")
    contract_sha = _sha256_bytes(contract_bytes)

    targets: dict[str, bytes | None] = {CANONICAL_CONTRACT_PATH.as_posix(): contract_bytes}
    for prior in lock.get("harness_contract", {}).get("adapters", {}).values():
        context_file = str(prior.get("context_file", "")).strip()
        if context_file:
            targets[context_file] = contract_bytes

    core_current = (
        str(lock.get("factory", {}).get("version", "")) == FACTORY_VERSION
        and str(lock.get("lock_schema_version", "")) == TARGET_LOCK_SCHEMA
        and str(lock.get("upgrade_contract", {}).get("version", "")) == UPGRADE_CONTRACT_VERSION
    )

    harness_path = project_root / ".project/evidence/harness-compatibility.json"
    if core_current and harness_path.is_file():
        targets[".project/evidence/harness-compatibility.json"] = harness_path.read_bytes()
    else:
        harness_evidence = _harness_evidence_target(lock, contract_sha)
        targets[".project/evidence/harness-compatibility.json"] = (
            json.dumps(harness_evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")

    host_lock = lock.get("host_integration")
    if isinstance(host_lock, dict) and host_lock.get("hosts"):
        for relative in (HOST_EVIDENCE_PATH.as_posix(), HOST_README_PATH.as_posix()):
            path = project_root / relative
            if path.is_file():
                targets[relative] = path.read_bytes()
        for item in host_lock.get("hosts", {}).values():
            relative = str(item.get("plan_path", "")).strip()
            if relative:
                path = project_root / relative
                if path.is_file():
                    targets[relative] = path.read_bytes()

    generation_path = project_root / ".project/generation.json"
    generation = _read_json(generation_path) if generation_path.is_file() else {}
    if core_current and generation_path.is_file():
        targets[".project/generation.json"] = generation_path.read_bytes()
    else:
        generation["factory_upgrade_contract"] = {
            "version": UPGRADE_CONTRACT_VERSION,
            "dry_run_required": True,
            "automatic_apply": False,
            "factory_owned_files_only": True,
            "last_planned_upgrade_id": upgrade_id,
        }
        targets[".project/generation.json"] = (
            json.dumps(generation, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")

    try:
        overlay_targets = render_overlay_targets(
            project_name=str(lock.get("project_name", project_root.name)),
            profile_id=str(lock.get("profile", {}).get("id", "")),
            factory_version=FACTORY_VERSION,
        )
    except OverlayError as exc:
        raise UpgradeError(str(exc)) from exc
    overlap = sorted(set(targets) & set(overlay_targets))
    if overlap:
        raise UpgradeError("Factory overlay collides with upgrade core targets: " + ", ".join(overlap))
    targets.update(overlay_targets)

    # B01/B06: per-profile skills are Factory-owned; include them in DryRun/upgrade targets.
    try:
        from .assembly import render_profile_skill  # local import to avoid cycle

        project_name = str(lock.get("project_name", project_root.name))
        profile_ids: list[str] = []
        main_pid = str((lock.get("profile") or {}).get("id", "")).strip()
        if main_pid and main_pid != "blank":
            profile_ids.append(main_pid)
        assembly = lock.get("assembly") or {}
        for pkg in assembly.get("packages") or []:
            pid = str(pkg.get("profile", "")).strip()
            if pid and pid not in profile_ids:
                profile_ids.append(pid)
        for pid in profile_ids:
            skill_rel = f"skills/{pid}/SKILL.md"
            if skill_rel in targets:
                continue
            skill_text = render_profile_skill(project_name, pid, FACTORY_VERSION)
            if not skill_text.endswith("\n"):
                skill_text += "\n"
            targets[skill_rel] = skill_text.encode("utf-8")
    except Exception as exc:  # pragma: no cover
        raise UpgradeError(f"Failed to render profile skills for upgrade: {exc}") from exc

    # Runtime-generated files are declared in DryRun but produced only after a real apply.
    targets[f".project/upgrades/{upgrade_id}/plan.json"] = None
    targets[".project/evidence/upgrade-verification.json"] = None
    targets[FACTORY_OVERLAY_MANIFEST_PATH.as_posix()] = None
    return targets


def _project_source_manifest_sha(project_root: Path) -> str:
    manifest = project_root / "PROJECT_MANIFEST.sha256"
    if not manifest.is_file():
        raise UpgradeError("PROJECT_MANIFEST.sha256 is missing.")
    return sha256_file(manifest)


def _validate_blueprint_provenance(project_root: Path, lock: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    blueprint_path = project_root / ".project/blueprint.yaml"
    if not blueprint_path.is_file():
        return ["Blueprint file .project/blueprint.yaml is missing."]
    blueprint = yaml.safe_load(blueprint_path.read_text(encoding="utf-8"))
    actual = _sha256_bytes(_json_bytes(blueprint))
    expected = str(lock.get("blueprint_sha256", ""))
    if expected and actual != expected:
        problems.append("Blueprint differs from the Project Lock; reconcile Blueprint provenance before upgrade.")
    return problems


def _diff_preview(relative: str, current: bytes | None, proposed: bytes | None) -> str | None:
    if proposed is None:
        return None
    try:
        before = (current or b"").decode("utf-8").splitlines()
        after = proposed.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        return None
    lines = list(
        difflib.unified_diff(
            before,
            after,
            fromfile=f"a/{relative}",
            tofile=f"b/{relative}",
            lineterm="",
            n=2,
        )
    )
    if not lines:
        return None
    if len(lines) > 80:
        lines = lines[:80] + ["... diff preview truncated ..."]
    return "\n".join(lines)


def plan_upgrade(project_root: Path, *, extension_set: Path | None = None) -> UpgradePlan:
    root = Path(project_root).resolve()
    lock_path = root / "project.lock.json"
    if not lock_path.is_file():
        raise UpgradeError("project.lock.json is required.")
    lock = _read_json(lock_path)
    try:
        extension_runtime = load_extension_runtime(extension_set)
        assert_upgrade_extension_set(extension_runtime, lock.get("extensions", []))
    except ExtensionError as exc:
        raise UpgradeError(str(exc)) from exc
    source_schema = str(lock.get("lock_schema_version", ""))
    if source_schema not in SUPPORTED_SOURCE_LOCKS:
        raise UpgradeError(f"Unsupported source lock schema {source_schema!r}; no migration contract exists.")
    project_name = str(lock.get("project_name", root.name))
    source_manifest_sha = _project_source_manifest_sha(root)
    upgrade_id = _portable_upgrade_id(project_name, source_manifest_sha, extension_runtime.extension_versions())
    targets = _render_targets(root, lock, upgrade_id)
    try:
        extension_targets = collect_extension_migration_targets(root, lock, extension_runtime)
    except ExtensionError as exc:
        raise UpgradeError(str(exc)) from exc
    overlap = sorted(set(targets) & set(extension_targets))
    if overlap:
        raise UpgradeError("Extension migration target collides with Factory Core: " + ", ".join(overlap))
    targets.update(extension_targets)
    targets[".project/extensions.lock.json"] = None
    expected = _source_expected_hashes(root, lock)

    changes: list[UpgradeChange] = []
    blocked = _validate_blueprint_provenance(root, lock)
    for relative, proposed in targets.items():
        path = root / relative
        current_bytes = path.read_bytes() if path.is_file() else None
        current_sha = _sha256_bytes(current_bytes) if current_bytes is not None else None
        expected_sha = expected.get(relative)
        proposed_sha = _sha256_bytes(proposed) if proposed is not None else None
        action = "ADD_DYNAMIC" if proposed is None else ("ADD" if current_sha is None else "REPLACE")
        conflict = False
        reason = "Factory-owned overlay refresh"
        if current_sha is not None and expected_sha and current_sha != expected_sha:
            conflict = True
            reason = "Factory-owned file diverged from its recorded preimage"
            blocked.append(f"Managed-file conflict: {relative}")
        if proposed is not None and current_sha == proposed_sha:
            action = "UNCHANGED"
            reason = "Already matches target overlay"
        changes.append(
            UpgradeChange(
                path=relative,
                action=action,
                ownership="factory-managed",
                current_sha256=current_sha,
                expected_prior_sha256=expected_sha,
                proposed_sha256=proposed_sha,
                conflict=conflict,
                reason=reason,
                diff_preview=_diff_preview(relative, current_bytes, proposed),
            )
        )

    registry = load_registry(extension_runtime=extension_runtime)
    if str(lock.get("profile", {}).get("id", "")) not in registry.profiles:
        blocked.append("Locked profile is unavailable in the current Factory registry.")
    for capability, locked_provider in lock.get("providers", {}).items():
        provider_id = str(locked_provider.get("id", ""))
        locked_version = str(locked_provider.get("version", ""))
        spec = registry.providers.get(provider_id)
        if spec is None or spec.capability != capability:
            blocked.append(f"Locked provider {provider_id!r} for {capability!r} is unavailable in the current registry.")
            continue
        try:
            runtime = inspect_provider(spec)
            if runtime.version != locked_version:
                blocked.append(
                    f"Locked provider {provider_id!r} expects {locked_version}, but runtime is {runtime.version}; "
                    "provider migration is outside this overlay upgrade."
                )
        except RegistryError as exc:
            blocked.append(str(exc))

    substantive = [c for c in changes if c.action not in {"UNCHANGED", "ADD_DYNAMIC"}]
    already_current = (
        str(lock.get("factory", {}).get("version", "")) == FACTORY_VERSION
        and source_schema == TARGET_LOCK_SCHEMA
        and bool(lock.get("upgrade_contract"))
        and isinstance(lock.get("managed_files"), dict)
    )
    if already_current:
        overlay_ok, overlay_failures = verify_factory_overlay_manifest(root)
        if not overlay_ok:
            blocked.extend(f"Factory Overlay Manifest: {item}" for item in overlay_failures)
    if already_current and not substantive and not blocked:
        changes = []
    risk = "MEDIUM" if substantive else "LOW"
    status = "BLOCKED" if blocked else ("CURRENT" if already_current and not substantive else "READY")
    base = {
        "schema_version": "0.1",
        "upgrade_id": upgrade_id,
        "project_name": project_name,
        "source_factory_version": str(lock.get("factory", {}).get("version", "unknown")),
        "source_factory_stage": str(lock.get("factory", {}).get("stage", "unknown")),
        "source_lock_schema": source_schema,
        "target_factory_version": FACTORY_VERSION,
        "target_factory_stage": FACTORY_STAGE,
        "target_lock_schema": TARGET_LOCK_SCHEMA,
        "migration_id": "factory-overlay-v3",
        "status": status,
        "risk": risk,
        "changes": [asdict(item) for item in changes],
        "blocked_reasons": sorted(set(blocked)),
        "verification": [
            "managed-file postimage hashes",
            "canonical/harness contract parity",
            "interactive Host plan integrity when configured",
            "long-running Runner plan integrity when configured",
            "profile verification suite",
            "Factory Overlay Manifest integrity",
        ],
        "rollback": {
            "type": "targeted-preimage-bundle",
            "scope": "only files changed by this upgrade",
            "independent_disaster_backup": False,
            "note": "This is an immediate rollback point, not an independent backup.",
        },
    }
    plan_sha = _sha256_bytes(_json_bytes(base))
    return UpgradePlan(
        schema_version="0.1",
        upgrade_id=upgrade_id,
        project_name=project_name,
        source_factory_version=base["source_factory_version"],
        source_factory_stage=base["source_factory_stage"],
        source_lock_schema=source_schema,
        target_factory_version=FACTORY_VERSION,
        target_factory_stage=FACTORY_STAGE,
        target_lock_schema=TARGET_LOCK_SCHEMA,
        migration_id="factory-overlay-v3",
        status=status,
        risk=risk,
        changes=tuple(changes),
        blocked_reasons=tuple(base["blocked_reasons"]),
        verification=tuple(base["verification"]),
        rollback=base["rollback"],
        plan_sha256=plan_sha,
    )


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _rollback_bundle_path(project_root: Path, upgrade_id: str) -> Path:
    return project_root.parent / ".project-factory-rollback" / f"{project_root.name}-{upgrade_id}.zip"


def _create_rollback_bundle(project_root: Path, plan: UpgradePlan) -> Path:
    bundle = _rollback_bundle_path(project_root, plan.upgrade_id)
    bundle.parent.mkdir(parents=True, exist_ok=True)
    if bundle.exists():
        raise UpgradeError(f"Rollback bundle already exists: {bundle}")
    inventory: dict[str, Any] = {
        "schema_version": "0.1",
        "project_name": plan.project_name,
        "upgrade_id": plan.upgrade_id,
        "plan_sha256": plan.plan_sha256,
        "preimages": {},
        "absent_before": [],
    }
    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for change in plan.changes:
            if change.action == "UNCHANGED":
                continue
            path = project_root / change.path
            if path.is_file():
                payload = path.read_bytes()
                inventory["preimages"][change.path] = _sha256_bytes(payload)
                archive.writestr(f"preimage/{change.path}", payload)
            else:
                inventory["absent_before"].append(change.path)
        # Project Lock always changes/finalizes during apply. The generation-time
        # PROJECT_MANIFEST is deliberately not rewritten by upgrades.
        for relative in ("project.lock.json",):
            path = project_root / relative
            if path.is_file() and relative not in inventory["preimages"]:
                payload = path.read_bytes()
                inventory["preimages"][relative] = _sha256_bytes(payload)
                archive.writestr(f"preimage/{relative}", payload)
        archive.writestr("ROLLBACK.json", json.dumps(inventory, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return bundle


def _assert_plan_fresh(project_root: Path, plan: UpgradePlan, *, extension_set: Path | None = None) -> None:
    current = plan_upgrade(project_root, extension_set=extension_set)
    if current.plan_sha256 != plan.plan_sha256 or current.status != "READY":
        raise UpgradeError("Upgrade plan is stale or no longer READY; run DryRun again.")


def _verify_after_apply(project_root: Path, lock: dict[str, Any], extension_runtime: ExtensionRuntime) -> dict[str, Any]:
    harness = verify_harness_contracts(project_root, lock.get("harness_contract", {}))
    if harness["status"] == "FAILED":
        raise UpgradeError("Harness contract verification failed after upgrade: " + "; ".join(harness["failures"]))
    host = verify_host_materialization(project_root, lock.get("host_integration"))
    if host["status"] == "FAILED":
        raise UpgradeError("Host integration verification failed after upgrade: " + "; ".join(host["failures"]))
    runner = verify_runner_materialization(project_root, lock.get("runner_integration"))
    if runner["status"] == "FAILED":
        raise UpgradeError("Runner integration verification failed after upgrade: " + "; ".join(runner["failures"]))
    registry = load_registry(extension_runtime=extension_runtime)
    profile_id = str(lock.get("profile", {}).get("id", ""))
    profile = registry.profiles.get(profile_id)
    if profile is None:
        raise UpgradeError(f"Locked profile {profile_id!r} is unavailable after upgrade.")
    try:
        locked = lock.get("providers", {}).get("project_scaffolding", {})
        provider_id = str(locked.get("id", ""))
        locked_version = str(locked.get("version", ""))
        spec = registry.providers.get(provider_id)
        if spec is None:
            raise UpgradeError(f"Locked scaffolding provider {provider_id!r} is unavailable.")
        runtime = inspect_provider(spec)
        if runtime.version != locked_version:
            raise UpgradeError(
                f"Locked scaffolding provider version {locked_version} differs from runtime {runtime.version}; "
                "provider migration requires a separate migration contract."
            )
        provider = SimpleNamespace(
            provider_id=runtime.spec.id,
            provider_version=runtime.version,
            executable=runtime.executable_path,
        )
        suite = build_verification_suite(profile.verification_recipe, lock["project_name"], provider, extension_runtime=extension_runtime)
        verification = execute_verification_suite(suite, project_root, provider)
        assert_required_gates(verification)
    except (RegistryError, VerificationError) as exc:
        raise UpgradeError(str(exc)) from exc
    receipt_path = Path(project_root) / ".project/extensions.lock.json"
    if receipt_path.is_file():
        extension_receipt = _read_json(receipt_path)
        extension_check = verify_extension_receipt(project_root, extension_receipt)
        if extension_check["status"] == "FAILED":
            raise UpgradeError("Extension verification failed after upgrade: " + "; ".join(extension_check["failures"]))
    else:
        extension_check = {"status": "VERIFIED", "failures": []}
    return {"harness": harness, "host": host, "runner": runner, "project_verification": verification, "extensions": extension_check}


def apply_upgrade(
    project_root: Path,
    *,
    confirm_plan_sha256: str,
    extension_set: Path | None = None,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    plan = plan_upgrade(root, extension_set=extension_set)
    if plan.status == "CURRENT":
        raise UpgradeError("Project is already current; no upgrade apply is required.")
    if plan.status != "READY":
        raise UpgradeError("Upgrade is BLOCKED: " + "; ".join(plan.blocked_reasons))
    if confirm_plan_sha256 != plan.plan_sha256:
        raise UpgradeError("Explicit confirmation hash does not match the current DryRun plan.")
    _assert_plan_fresh(root, plan, extension_set=extension_set)
    rollback_bundle = _create_rollback_bundle(root, plan)
    rollback_sha = sha256_file(rollback_bundle)

    lock = _read_json(root / "project.lock.json")
    try:
        extension_runtime = load_extension_runtime(extension_set)
        assert_upgrade_extension_set(extension_runtime, lock.get("extensions", []))
        extension_targets = collect_extension_migration_targets(root, lock, extension_runtime)
    except ExtensionError as exc:
        raise UpgradeError(str(exc)) from exc
    targets = _render_targets(root, lock, plan.upgrade_id)
    overlap = sorted(set(targets) & set(extension_targets))
    if overlap:
        raise UpgradeError("Extension migration target collides with Factory Core: " + ", ".join(overlap))
    targets.update(extension_targets)
    targets[".project/extensions.lock.json"] = None
    target_hashes: dict[str, str] = {}
    try:
        for relative, payload in targets.items():
            if payload is None:
                continue
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            target_hashes[relative] = _sha256_bytes(payload)

        # Rebuild harness lock from the upgraded evidence rather than preserving stale hashes.
        harness_evidence = _read_json(root / ".project/evidence/harness-compatibility.json")
        lock["harness_contract"] = {
            "status": harness_evidence["status"],
            "canonical_contract": harness_evidence["canonical_contract"],
            "adapters": harness_evidence["adapters"],
            "runtime_verified": False,
        }
        try:
            extension_receipt = build_existing_extension_receipt(root, extension_runtime)
        except ExtensionError as exc:
            raise UpgradeError(str(exc)) from exc
        _write_json(root / ".project/extensions.lock.json", extension_receipt)
        lock["extension_contract"] = {
            "api_version": "1",
            "automatic_code_loading": False,
            "state_required_for_reverification": bool(extension_runtime.extensions),
        }
        lock["extensions"] = [item.receipt() for item in extension_runtime.extensions]
        lock["extension_artifacts"] = list(extension_receipt["artifacts"])
        lock.setdefault("host_integration", None)
        lock.setdefault("runner_integration", None)
        lock["lock_schema_version"] = TARGET_LOCK_SCHEMA
        lock["factory"] = {"version": FACTORY_VERSION, "stage": FACTORY_STAGE}
        lock["managed_files"] = collect_managed_file_hashes(root, managed_paths_from_lock(lock))
        upgrade_record = {
            "upgrade_id": plan.upgrade_id,
            "migration_id": plan.migration_id,
            "source_factory_version": plan.source_factory_version,
            "target_factory_version": FACTORY_VERSION,
            "plan_sha256": plan.plan_sha256,
            "risk": plan.risk,
            "rollback_bundle_sha256": rollback_sha,
            "applied_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        history = list(lock.get("upgrade_history", []))
        history.append(upgrade_record)
        lock["upgrade_history"] = history
        lock["upgrade_contract"] = {
            "version": UPGRADE_CONTRACT_VERSION,
            "dry_run_required": True,
            "automatic_apply": False,
            "rollback_before_apply": True,
            "business_files_outside_overlay": True,
        }
        _write_json(root / "project.lock.json", lock)

        # Persist the exact approved plan only after mutation has begun and a rollback bundle exists.
        _write_json(root / f".project/upgrades/{plan.upgrade_id}/plan.json", plan.to_dict())
        verification = _verify_after_apply(root, lock, extension_runtime)
        evidence = {
            "schema_version": "0.1",
            "status": verification["project_verification"]["status"],
            "upgrade_id": plan.upgrade_id,
            "plan_sha256": plan.plan_sha256,
            "risk": plan.risk,
            "rollback_bundle": {
                "filename": rollback_bundle.name,
                "sha256": rollback_sha,
                "independent_disaster_backup": False,
            },
            "claims": {
                "managed_file_postimages": "VERIFIED",
                "factory_overlay_manifest": "VERIFIED",
                "harness_contract_parity": verification["harness"]["status"],
                "runner_integration": verification["runner"]["status"],
                "project_verification": verification["project_verification"]["status"],
                "extensions": verification["extensions"]["status"],
            },
            "limitations": [
                "Rollback bundle is a local immediate-undo artifact, not an independent disaster backup.",
                "Business/source files were not rewritten or re-baselined by this migration.",
                "PROJECT_MANIFEST.sha256 remains the generation-time snapshot; upgrade integrity uses the Factory Overlay Manifest.",
            ],
        }
        _write_json(root / ".project/evidence/upgrade-verification.json", evidence)
        lock["managed_files"] = collect_managed_file_hashes(root, managed_paths_from_lock(lock))
        lock["verification"] = {
            "status": verification["project_verification"]["status"],
            "suite": verification["project_verification"]["suite"],
            "claim_summary": verification["project_verification"]["claim_summary"],
        }
        _write_json(root / "project.lock.json", lock)
        overlay_paths = list(managed_paths_from_lock(lock)) + [
            "project.lock.json",
            f".project/upgrades/{plan.upgrade_id}/plan.json",
            ".project/evidence/upgrade-verification.json",
        ]
        write_factory_overlay_manifest(root, overlay_paths)
        overlay_ok, failures = verify_factory_overlay_manifest(root)
        if not overlay_ok:
            raise UpgradeError("Post-upgrade Factory Overlay Manifest failed: " + "; ".join(failures))
        postimage_receipt = _write_postimage_receipt(root, rollback_bundle)
        return {
            "status": "APPLIED",
            "upgrade_id": plan.upgrade_id,
            "plan_sha256": plan.plan_sha256,
            "risk": plan.risk,
            "rollback_bundle": str(rollback_bundle),
            "rollback_bundle_sha256": rollback_sha,
            "rollback_postimage_receipt": str(postimage_receipt),
            "rollback_postimage_receipt_sha256": sha256_file(postimage_receipt),
            "verification": evidence,
        }
    except Exception:
        # Do not attempt hidden automatic rollback. Preserve the rollback bundle and surface failure.
        raise


def _write_postimage_receipt(project_root: Path, rollback_bundle: Path) -> Path:
    with zipfile.ZipFile(rollback_bundle, "r") as archive:
        inventory = json.loads(archive.read("ROLLBACK.json"))
    paths = list(inventory.get("preimages", {})) + list(inventory.get("absent_before", []))
    postimages: dict[str, str | None] = {}
    for relative in dict.fromkeys(paths):
        path = project_root / relative
        postimages[relative] = sha256_file(path) if path.is_file() else None
    receipt = {
        "schema_version": "0.1",
        "project_name": project_root.name,
        "upgrade_id": inventory.get("upgrade_id"),
        "plan_sha256": inventory.get("plan_sha256"),
        "rollback_bundle_sha256": sha256_file(rollback_bundle),
        "postimages": postimages,
    }
    receipt_path = rollback_bundle.with_suffix(".post.json")
    _write_json(receipt_path, receipt)
    return receipt_path


def rollback_upgrade(project_root: Path, rollback_bundle: Path, *, confirm_bundle_sha256: str) -> dict[str, Any]:
    root = Path(project_root).resolve()
    bundle = Path(rollback_bundle).resolve()
    if not bundle.is_file():
        raise UpgradeError(f"Rollback bundle does not exist: {bundle}")
    actual_sha = sha256_file(bundle)
    if confirm_bundle_sha256 != actual_sha:
        raise UpgradeError("Explicit rollback confirmation hash does not match the rollback bundle.")
    receipt_path = bundle.with_suffix(".post.json")
    if not receipt_path.is_file():
        raise UpgradeError("Rollback postimage receipt is missing; refuse to overwrite an unknown current state.")
    receipt = _read_json(receipt_path)
    if receipt.get("rollback_bundle_sha256") != actual_sha:
        raise UpgradeError("Rollback postimage receipt does not match the rollback bundle.")
    conflicts: list[str] = []
    for relative, expected_post in receipt.get("postimages", {}).items():
        path = root / relative
        actual_post = sha256_file(path) if path.is_file() else None
        if actual_post != expected_post:
            conflicts.append(relative)
    if conflicts:
        raise UpgradeError(
            "Rollback would overwrite post-upgrade changes in: " + ", ".join(sorted(conflicts))
        )
    with zipfile.ZipFile(bundle, "r") as archive:
        bad = archive.testzip()
        if bad:
            raise UpgradeError(f"Rollback bundle CRC failed for {bad}")
        inventory = json.loads(archive.read("ROLLBACK.json"))
        if inventory.get("project_name") != root.name:
            raise UpgradeError("Rollback bundle belongs to a different project.")
        for relative, expected_sha in inventory.get("preimages", {}).items():
            payload = archive.read(f"preimage/{relative}")
            if _sha256_bytes(payload) != expected_sha:
                raise UpgradeError(f"Rollback preimage hash mismatch: {relative}")
        # Restore preimages first, then explicitly remove files that did not exist before the upgrade.
        for relative in inventory.get("preimages", {}):
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(archive.read(f"preimage/{relative}"))
        for relative in inventory.get("absent_before", []):
            path = root / relative
            if path.is_file():
                path.unlink()
            parent = path.parent
            while parent != root and parent.exists() and not any(parent.iterdir()):
                parent.rmdir()
                parent = parent.parent
    return {
        "status": "ROLLED_BACK",
        "bundle_sha256": actual_sha,
        "project_name": root.name,
        "project_lock_sha256": sha256_file(root / "project.lock.json") if (root / "project.lock.json").is_file() else None,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DryRun, apply, or rollback a Project Factory overlay upgrade.")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("plan")
    p.add_argument("project_root", type=Path)
    p.add_argument("--extension-set", type=Path)
    a = sub.add_parser("apply")
    a.add_argument("project_root", type=Path)
    a.add_argument("--confirm-plan", required=True)
    a.add_argument("--extension-set", type=Path)
    r = sub.add_parser("rollback")
    r.add_argument("project_root", type=Path)
    r.add_argument("rollback_bundle", type=Path)
    r.add_argument("--confirm-bundle", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "plan":
            result = plan_upgrade(args.project_root, extension_set=args.extension_set).to_dict()
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
            return 0 if result["status"] == "READY" else 2
        if args.command == "apply":
            print(json.dumps(apply_upgrade(args.project_root, confirm_plan_sha256=args.confirm_plan, extension_set=args.extension_set), ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        print(json.dumps(rollback_upgrade(args.project_root, args.rollback_bundle, confirm_bundle_sha256=args.confirm_bundle), ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (UpgradeError, FactoryError, ExtensionError) as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}, ensure_ascii=False, indent=2, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
