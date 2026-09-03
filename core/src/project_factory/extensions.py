from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import json
import os
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

import yaml
from jsonschema import Draft202012Validator


EXTENSION_API_VERSION = "1"
EXTENSION_SET_SCHEMA_VERSION = "0.1"
ENTRY_POINT_GROUP = "project_factory.extensions"
_SCHEMA_ROOT = Path(__file__).resolve().parent / "schema_data"
_MANIFEST_SCHEMA = _SCHEMA_ROOT / "extension-manifest.schema.json"
_SET_SCHEMA = _SCHEMA_ROOT / "extension-set.schema.json"


class ExtensionError(RuntimeError):
    """Raised when an extension is unsafe, incompatible, stale, or invalid."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ExtensionError(f"Expected JSON object: {path}")
    return value


def _load_schema(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(value)
    return value


def _validate_json(value: dict[str, Any], schema_path: Path, label: str) -> None:
    validator = Draft202012Validator(_load_schema(schema_path))
    issues = sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path))
    if issues:
        first = issues[0]
        path = "/" + "/".join(str(item) for item in first.absolute_path)
        raise ExtensionError(f"{label} is invalid at {path}: {first.message}")


def _safe_relative(value: str, *, label: str) -> Path:
    path = Path(value)
    if not value or path.is_absolute() or ".." in path.parts:
        raise ExtensionError(f"Unsafe {label}: {value!r}")
    return path


def _canonical_dist_name(value: str) -> str:
    return value.casefold().replace("_", "-").replace(".", "-")


@dataclass(frozen=True)
class ProjectArtifact:
    extension_id: str
    id: str
    kind: str
    source: Path
    target: Path


@dataclass(frozen=True)
class ExtensionManifest:
    path: Path
    id: str
    version: str
    mode: str
    description: str
    manifest_sha256: str
    registry: dict[str, tuple[dict[str, Any], ...]]
    project_artifacts: tuple[ProjectArtifact, ...]
    code: dict[str, str] | None


FormulaAdapter = Callable[..., None]
ScaffoldRecipe = Callable[..., Any]
VerificationBuilder = Callable[..., Any]
MigrationHook = Callable[..., Mapping[str, bytes | str | None]]


@dataclass
class ExtensionRegistrar:
    extension_id: str
    formula_adapters: dict[str, FormulaAdapter] = field(default_factory=dict)
    scaffold_recipes: dict[str, ScaffoldRecipe] = field(default_factory=dict)
    verification_builders: dict[str, VerificationBuilder] = field(default_factory=dict)
    migration_hooks: dict[str, MigrationHook] = field(default_factory=dict)

    def _register(self, bucket: dict[str, Any], contribution_id: str, value: Any, *, kind: str) -> None:
        prefix = self.extension_id + "."
        if not contribution_id.startswith(prefix):
            raise ExtensionError(
                f"Trusted code extension {self.extension_id!r} must namespace {kind} id {contribution_id!r} with {prefix!r}."
            )
        if contribution_id in bucket:
            raise ExtensionError(f"Duplicate {kind} id from extension {self.extension_id!r}: {contribution_id}")
        if not callable(value):
            raise ExtensionError(f"{kind} {contribution_id!r} must be callable.")
        bucket[contribution_id] = value

    def formula_adapter(self, contribution_id: str, adapter: FormulaAdapter) -> None:
        self._register(self.formula_adapters, contribution_id, adapter, kind="Formula adapter")

    def scaffold_recipe(self, contribution_id: str, handler: ScaffoldRecipe) -> None:
        self._register(self.scaffold_recipes, contribution_id, handler, kind="scaffold recipe")

    def verification_builder(self, contribution_id: str, builder: VerificationBuilder) -> None:
        self._register(self.verification_builders, contribution_id, builder, kind="verification builder")

    def migration_hook(self, contribution_id: str, hook: MigrationHook) -> None:
        self._register(self.migration_hooks, contribution_id, hook, kind="migration hook")


@dataclass(frozen=True)
class LoadedExtension:
    manifest: ExtensionManifest
    trust: str
    distribution: str | None
    distribution_version: str | None
    distribution_sha256: str | None
    distribution_file_count: int
    entry_point: str | None
    contribution_sha256: str

    def receipt(self) -> dict[str, Any]:
        return {
            "id": self.manifest.id,
            "version": self.manifest.version,
            "mode": self.manifest.mode,
            "trust": self.trust,
            "manifest_sha256": self.manifest.manifest_sha256,
            "distribution": self.distribution,
            "distribution_version": self.distribution_version,
            "distribution_sha256": self.distribution_sha256,
            "distribution_file_count": self.distribution_file_count,
            "entry_point": self.entry_point,
            "contribution_sha256": self.contribution_sha256,
        }


@dataclass
class ExtensionRuntime:
    state_path: Path | None = None
    extensions: tuple[LoadedExtension, ...] = ()
    registry_contributions: dict[str, list[dict[str, Any]]] = field(
        default_factory=lambda: {key: [] for key in ("capabilities", "providers", "profiles", "formulas", "policies")}
    )
    project_artifacts: tuple[ProjectArtifact, ...] = ()
    formula_adapters: dict[str, FormulaAdapter] = field(default_factory=dict)
    scaffold_recipes: dict[str, ScaffoldRecipe] = field(default_factory=dict)
    verification_builders: dict[str, VerificationBuilder] = field(default_factory=dict)
    migration_hooks: dict[str, MigrationHook] = field(default_factory=dict)

    def receipt(self) -> dict[str, Any]:
        return {
            "schema_version": "0.1",
            "factory_api": EXTENSION_API_VERSION,
            "extensions": [item.receipt() for item in self.extensions],
            "automatic_code_loading": False,
        }

    def extension_versions(self) -> dict[str, str]:
        return {item.manifest.id: item.manifest.version for item in self.extensions}


EMPTY_EXTENSION_RUNTIME = ExtensionRuntime()


def load_extension_manifest(path: Path) -> ExtensionManifest:
    manifest_path = Path(path).resolve()
    if not manifest_path.is_file():
        raise ExtensionError(f"Extension manifest not found: {manifest_path}")
    raw = manifest_path.read_bytes()
    try:
        data = yaml.safe_load(raw.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise ExtensionError(f"Extension manifest is not valid UTF-8: {manifest_path}") from exc
    if not isinstance(data, dict):
        raise ExtensionError("Extension manifest must contain a mapping.")
    _validate_json(data, _MANIFEST_SCHEMA, "Extension manifest")

    ext = data["extension"]
    extension_id = str(ext["id"])
    mode = str(ext["mode"])
    contributes = data.get("contributes", {})
    registry_raw = contributes.get("registry", {}) or {}
    if not isinstance(registry_raw, dict):
        raise ExtensionError("contributes.registry must be a mapping.")
    registry: dict[str, tuple[dict[str, Any], ...]] = {}
    for kind in ("capabilities", "providers", "profiles", "formulas", "policies"):
        items = registry_raw.get(kind, []) or []
        if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
            raise ExtensionError(f"Extension registry contribution {kind!r} must be a list of mappings.")
        if kind == "providers" and items and mode != "trusted-code":
            raise ExtensionError("Declarative extensions may not add executable Providers; use explicit trusted-code mode.")
        for item in items:
            contribution_id = str(item.get("id", ""))
            if not contribution_id.startswith(extension_id + "."):
                raise ExtensionError(
                    f"Extension registry id {contribution_id!r} must be namespaced as {extension_id}.<name>."
                )
        registry[kind] = tuple(dict(item) for item in items)

    artifacts: list[ProjectArtifact] = []
    base = manifest_path.parent.resolve()
    seen_artifact_ids: set[str] = set()
    seen_targets: set[str] = set()
    for item in contributes.get("project_artifacts", []) or []:
        artifact_id = str(item["id"])
        if artifact_id in seen_artifact_ids:
            raise ExtensionError(f"Duplicate project artifact id: {artifact_id}")
        seen_artifact_ids.add(artifact_id)
        source_rel = _safe_relative(str(item["source"]), label="artifact source")
        target_rel = _safe_relative(str(item["target"]), label="artifact target")
        if target_rel.as_posix() in seen_targets:
            raise ExtensionError(f"Duplicate project artifact target: {target_rel.as_posix()}")
        seen_targets.add(target_rel.as_posix())
        source = (base / source_rel).resolve()
        try:
            source.relative_to(base)
        except ValueError as exc:
            raise ExtensionError(f"Project artifact source escapes the extension directory: {source_rel}") from exc
        if not source.is_file():
            raise ExtensionError(f"Project artifact source not found: {source_rel}")
        artifacts.append(
            ProjectArtifact(
                extension_id=extension_id,
                id=artifact_id,
                kind=str(item["kind"]),
                source=source,
                target=target_rel,
            )
        )

    code = None
    if data.get("code") is not None:
        code = {str(key): str(value) for key, value in dict(data["code"]).items()}
        search_path = code.get("search_path")
        if search_path:
            rel = _safe_relative(search_path, label="trusted-code search_path")
            resolved = (base / rel).resolve()
            try:
                resolved.relative_to(base)
            except ValueError as exc:
                raise ExtensionError("trusted-code search_path must remain inside the extension directory.") from exc
            if not resolved.is_dir():
                raise ExtensionError(f"trusted-code search_path not found: {search_path}")
            code["search_path"] = str(resolved)

    return ExtensionManifest(
        path=manifest_path,
        id=extension_id,
        version=str(ext["version"]),
        mode=mode,
        description=str(ext["description"]),
        manifest_sha256=_sha256_bytes(raw),
        registry=registry,
        project_artifacts=tuple(artifacts),
        code=code,
    )


def _default_extension_set() -> dict[str, Any]:
    return {"schema_version": EXTENSION_SET_SCHEMA_VERSION, "factory_api": EXTENSION_API_VERSION, "extensions": []}


def load_extension_set(path: Path) -> dict[str, Any]:
    state_path = Path(path).resolve()
    if not state_path.exists():
        return _default_extension_set()
    data = _read_json(state_path)
    _validate_json(data, _SET_SCHEMA, "Extension Set")
    ids = [str(item["id"]) for item in data["extensions"]]
    if len(ids) != len(set(ids)):
        raise ExtensionError("Extension Set contains duplicate extension ids.")
    return data


def _portable_manifest_reference(state_path: Path, manifest_path: Path) -> str:
    state_parent = state_path.resolve().parent
    manifest = manifest_path.resolve()
    try:
        return manifest.relative_to(state_parent).as_posix()
    except ValueError:
        return str(manifest)


def _resolve_manifest_reference(state_path: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path.resolve()
    return (state_path.resolve().parent / path).resolve()


@dataclass(frozen=True)
class ExtensionSetPlan:
    schema_version: str
    action: str
    extension_id: str
    prior_state_sha256: str | None
    proposed_state: dict[str, Any]
    plan_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _state_sha(path: Path) -> str | None:
    return sha256_file(path) if path.is_file() else None


def _make_plan(action: str, extension_id: str, prior_sha: str | None, proposed: dict[str, Any]) -> ExtensionSetPlan:
    base = {
        "schema_version": "0.1",
        "action": action,
        "extension_id": extension_id,
        "prior_state_sha256": prior_sha,
        "proposed_state": proposed,
    }
    digest = _sha256_bytes(_json_bytes(base))
    return ExtensionSetPlan(plan_sha256=digest, **base)


def plan_add_extension(state_path: Path, manifest_path: Path, *, trust_code: bool = False) -> ExtensionSetPlan:
    state_path = Path(state_path).resolve()
    state = load_extension_set(state_path)
    manifest = load_extension_manifest(manifest_path)
    if manifest.mode == "trusted-code" and not trust_code:
        raise ExtensionError("Trusted-code extension requires explicit trust_code=True during registration.")
    trust = "trusted-code" if manifest.mode == "trusted-code" else "declarative"
    entries = [dict(item) for item in state["extensions"] if str(item["id"]) != manifest.id]
    entries.append(
        {
            "id": manifest.id,
            "version": manifest.version,
            "mode": manifest.mode,
            "manifest": _portable_manifest_reference(state_path, manifest.path),
            "manifest_sha256": manifest.manifest_sha256,
            "enabled": True,
            "trust": trust,
        }
    )
    entries.sort(key=lambda item: str(item["id"]))
    proposed = {**state, "extensions": entries}
    return _make_plan("ADD_OR_REPLACE", manifest.id, _state_sha(state_path), proposed)


def plan_extension_state(state_path: Path, extension_id: str, *, action: str) -> ExtensionSetPlan:
    if action not in {"ENABLE", "DISABLE", "REMOVE"}:
        raise ExtensionError(f"Unsupported extension state action: {action}")
    state_path = Path(state_path).resolve()
    state = load_extension_set(state_path)
    found = False
    entries: list[dict[str, Any]] = []
    for raw in state["extensions"]:
        item = dict(raw)
        if str(item["id"]) == extension_id:
            found = True
            if action == "REMOVE":
                continue
            item["enabled"] = action == "ENABLE"
        entries.append(item)
    if not found:
        raise ExtensionError(f"Extension {extension_id!r} is not registered in the Extension Set.")
    proposed = {**state, "extensions": entries}
    return _make_plan(action, extension_id, _state_sha(state_path), proposed)


def write_extension_plan(path: Path, plan: ExtensionSetPlan) -> None:
    target = Path(path)
    if target.exists():
        raise ExtensionError(f"Refusing to overwrite existing plan file: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_extension_plan(path: Path) -> ExtensionSetPlan:
    data = _read_json(Path(path))
    supplied = str(data.pop("plan_sha256", ""))
    expected = _sha256_bytes(_json_bytes(data))
    if not supplied or supplied != expected:
        raise ExtensionError("Extension Set plan hash is invalid or stale.")
    return ExtensionSetPlan(plan_sha256=supplied, **data)


def apply_extension_plan(state_path: Path, plan: ExtensionSetPlan, *, confirm_plan_sha256: str) -> dict[str, Any]:
    state_path = Path(state_path).resolve()
    if confirm_plan_sha256 != plan.plan_sha256:
        raise ExtensionError("Explicit extension plan confirmation hash does not match.")
    if _state_sha(state_path) != plan.prior_state_sha256:
        raise ExtensionError("Extension Set changed after DryRun; create a new plan.")
    _validate_json(plan.proposed_state, _SET_SCHEMA, "Proposed Extension Set")
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(plan.proposed_state, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=state_path.parent, delete=False) as handle:
        handle.write(payload)
        temp_path = Path(handle.name)
    os.replace(temp_path, state_path)
    return {
        "status": "APPLIED",
        "action": plan.action,
        "extension_id": plan.extension_id,
        "plan_sha256": plan.plan_sha256,
        "state_sha256": sha256_file(state_path),
        "package_or_source_deleted": False,
    }


def _find_distribution(code: Mapping[str, str]) -> tuple[metadata.Distribution, metadata.EntryPoint]:
    expected_name = _canonical_dist_name(code["distribution"])
    expected_version = code["distribution_version"]
    group = code["entry_point_group"]
    name = code["entry_point_name"]
    search_path = code.get("search_path")
    distributions = metadata.distributions(path=[search_path]) if search_path else metadata.distributions()
    matches: list[tuple[metadata.Distribution, metadata.EntryPoint]] = []
    for dist in distributions:
        dist_name = dist.metadata.get("Name") or ""
        if _canonical_dist_name(dist_name) != expected_name:
            continue
        if str(dist.version) != expected_version:
            raise ExtensionError(
                f"Trusted extension distribution {dist_name!r} has version {dist.version!r}; expected {expected_version!r}."
            )
        for entry in dist.entry_points:
            if entry.group == group and entry.name == name:
                matches.append((dist, entry))
    if not matches:
        raise ExtensionError(
            f"Trusted extension entry point {group}:{name} from {code['distribution']}@{expected_version} is unavailable."
        )
    if len(matches) != 1:
        raise ExtensionError(f"Trusted extension entry point {group}:{name} is ambiguous.")
    return matches[0]




_VOLATILE_DISTRIBUTION_FILES = {
    "INSTALLER",
    "REQUESTED",
    "RECORD",
    "direct_url.json",
}


def _stable_distribution_member(relative: Any) -> bool:
    normalized = str(relative).replace("\\", "/")
    parts = normalized.split("/")
    if "__pycache__" in parts or normalized.endswith((".pyc", ".pyo")):
        return False
    if ".dist-info/" in normalized and parts[-1] in _VOLATILE_DISTRIBUTION_FILES:
        return False
    return True


def _distribution_fingerprint(dist: metadata.Distribution) -> tuple[str, int]:
    # Fingerprint publisher/package content, not installer/runtime by-products.
    # pip may add direct_url.json, INSTALLER, REQUESTED, rewrite RECORD, and
    # create __pycache__; including those would make the same wheel/code look
    # different after a harmless reinstall to another path.
    files = [item for item in (dist.files or []) if _stable_distribution_member(item)]
    if not files:
        raise ExtensionError(
            f"Trusted extension distribution {dist.metadata.get('Name', '')!r} has no stable file inventory; "
            "refuse to trust code without a bounded distribution fingerprint."
        )
    records: list[tuple[str, str]] = []
    for relative in sorted(files, key=lambda item: str(item)):
        path = Path(dist.locate_file(relative))
        if not path.is_file():
            raise ExtensionError(f"Trusted extension distribution file is missing: {relative}")
        records.append((str(relative).replace("\\", "/"), sha256_file(path)))
    return _sha256_bytes(_json_bytes(records)), len(records)

def _load_entry_point(entry: metadata.EntryPoint, search_path: str | None) -> Any:
    inserted = False
    if search_path and search_path not in sys.path:
        sys.path.insert(0, search_path)
        inserted = True
    try:
        return entry.load()
    finally:
        if inserted:
            try:
                sys.path.remove(search_path)
            except ValueError:
                pass


def _merge_handlers(target: dict[str, Any], source: Mapping[str, Any], *, kind: str) -> None:
    overlap = sorted(set(target) & set(source))
    if overlap:
        raise ExtensionError(f"Duplicate {kind} contribution(s): {', '.join(overlap)}")
    target.update(source)


def load_extension_runtime(state_path: Path | None) -> ExtensionRuntime:
    if state_path is None:
        return ExtensionRuntime()
    state_path = Path(state_path).resolve()
    state = load_extension_set(state_path)
    runtime = ExtensionRuntime(state_path=state_path)
    loaded: list[LoadedExtension] = []
    artifacts: list[ProjectArtifact] = []
    artifact_targets: set[str] = set()

    for entry in state["extensions"]:
        if not entry["enabled"]:
            continue
        manifest_path = _resolve_manifest_reference(state_path, str(entry["manifest"]))
        manifest = load_extension_manifest(manifest_path)
        if manifest.manifest_sha256 != entry["manifest_sha256"]:
            raise ExtensionError(f"Extension manifest changed after registration: {manifest.id}")
        for key in ("id", "version", "mode"):
            if str(entry[key]) != str(getattr(manifest, key)):
                raise ExtensionError(f"Extension Set {key} differs from manifest for {manifest.id!r}.")
        if entry["trust"] == "trusted-code" and manifest.mode != "trusted-code":
            raise ExtensionError(f"Extension {manifest.id!r} has inconsistent trust mode.")
        if manifest.mode == "trusted-code" and entry["trust"] != "trusted-code":
            raise ExtensionError(f"Trusted-code extension {manifest.id!r} is not explicitly trusted.")

        for kind, items in manifest.registry.items():
            runtime.registry_contributions[kind].extend(dict(item) for item in items)
        for artifact in manifest.project_artifacts:
            key = f"{artifact.extension_id}/{artifact.target.as_posix()}"
            if key in artifact_targets:
                raise ExtensionError(f"Duplicate project artifact target across extensions: {key}")
            artifact_targets.add(key)
            artifacts.append(artifact)

        dist_name = None
        dist_version = None
        dist_sha = None
        dist_file_count = 0
        entry_identity = None
        registrar = ExtensionRegistrar(manifest.id)
        if manifest.mode == "trusted-code":
            assert manifest.code is not None
            dist, entry_point = _find_distribution(manifest.code)
            dist_sha, dist_file_count = _distribution_fingerprint(dist)
            loaded_object = _load_entry_point(entry_point, manifest.code.get("search_path"))
            if callable(loaded_object):
                loaded_object(registrar)
            elif hasattr(loaded_object, "register") and callable(loaded_object.register):
                loaded_object.register(registrar)
            else:
                raise ExtensionError(
                    f"Trusted extension entry point {entry_point.name!r} must be callable or expose register()."
                )
            dist_name = dist.metadata.get("Name") or manifest.code["distribution"]
            dist_version = str(dist.version)
            entry_identity = f"{entry_point.group}:{entry_point.name}={entry_point.value}"
            _merge_handlers(runtime.formula_adapters, registrar.formula_adapters, kind="Formula adapter")
            _merge_handlers(runtime.scaffold_recipes, registrar.scaffold_recipes, kind="scaffold recipe")
            _merge_handlers(runtime.verification_builders, registrar.verification_builders, kind="verification builder")
            _merge_handlers(runtime.migration_hooks, registrar.migration_hooks, kind="migration hook")

        contribution_payload = {
            "registry": manifest.registry,
            "artifacts": [
                {"id": item.id, "kind": item.kind, "target": item.target.as_posix(), "sha256": sha256_file(item.source)}
                for item in manifest.project_artifacts
            ],
            "handlers": {
                "formula_adapters": sorted(registrar.formula_adapters),
                "scaffold_recipes": sorted(registrar.scaffold_recipes),
                "verification_builders": sorted(registrar.verification_builders),
                "migration_hooks": sorted(registrar.migration_hooks),
            },
        }
        loaded.append(
            LoadedExtension(
                manifest=manifest,
                trust=str(entry["trust"]),
                distribution=dist_name,
                distribution_version=dist_version,
                distribution_sha256=dist_sha,
                distribution_file_count=dist_file_count,
                entry_point=entry_identity,
                contribution_sha256=_sha256_bytes(_json_bytes(contribution_payload)),
            )
        )

    runtime.extensions = tuple(loaded)
    runtime.project_artifacts = tuple(artifacts)
    return runtime


def materialize_extension_artifacts(project_root: Path, runtime: ExtensionRuntime) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for artifact in runtime.project_artifacts:
        target = Path(project_root) / ".project" / "extensions" / artifact.extension_id / artifact.target
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise ExtensionError(f"Extension artifact would overwrite an existing file: {target}")
        payload = artifact.source.read_bytes()
        target.write_bytes(payload)
        records.append(
            {
                "extension_id": artifact.extension_id,
                "id": artifact.id,
                "kind": artifact.kind,
                "path": target.relative_to(project_root).as_posix(),
                "sha256": _sha256_bytes(payload),
            }
        )
    return {"schema_version": "0.1", "extensions": [item.receipt() for item in runtime.extensions], "artifacts": records}


def verify_extension_receipt(project_root: Path, receipt: Mapping[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    for item in receipt.get("artifacts", []):
        relative = str(item.get("path", ""))
        rel = Path(relative)
        if not relative or "\\" in relative or rel.is_absolute() or ".." in rel.parts:
            failures.append(f"Unsafe extension artifact path: {relative}")
            continue
        path = Path(project_root) / rel
        if not path.is_file():
            failures.append(f"Missing extension artifact: {item.get('path')}")
        elif sha256_file(path) != item.get("sha256"):
            failures.append(f"Extension artifact hash mismatch: {item.get('path')}")
    return {"status": "VERIFIED" if not failures else "FAILED", "failures": failures}


def assert_runtime_matches_lock(runtime: ExtensionRuntime, locked: Iterable[Mapping[str, Any]]) -> None:
    expected = {str(item.get("id")): dict(item) for item in locked}
    actual = {item.manifest.id: item.receipt() for item in runtime.extensions}
    if set(expected) != set(actual):
        raise ExtensionError(
            f"Enabled Extension Set does not match Project Lock: expected ids {sorted(expected)}, actual ids {sorted(actual)}"
        )
    for extension_id, prior in expected.items():
        current = actual[extension_id]
        for key in ("version", "contribution_sha256", "distribution_version", "distribution_sha256"):
            prior_value = prior.get(key)
            current_value = current.get(key)
            if prior_value is not None and prior_value != current_value:
                raise ExtensionError(
                    f"Extension {extension_id!r} {key} differs from Project Lock: expected {prior_value!r}, actual {current_value!r}"
                )


def collect_extension_migration_targets(
    project_root: Path,
    lock: Mapping[str, Any],
    runtime: ExtensionRuntime,
) -> dict[str, bytes | None]:
    locked = {str(item.get("id")): str(item.get("version")) for item in lock.get("extensions", [])}
    current = runtime.extension_versions()
    targets: dict[str, bytes | None] = {}
    for extension_id, source_version in locked.items():
        target_version = current.get(extension_id)
        if target_version is None:
            raise ExtensionError(f"Project requires extension {extension_id!r}, but it is not enabled in the supplied Extension Set.")
        if source_version == target_version:
            continue
        hook_id = extension_id + ".migration"
        hook = runtime.migration_hooks.get(hook_id)
        if hook is None:
            raise ExtensionError(
                f"Extension {extension_id!r} requires migration {source_version} -> {target_version}, but {hook_id!r} is unavailable."
            )
        raw = hook(Path(project_root), dict(lock), source_version, target_version)
        if not isinstance(raw, Mapping):
            raise ExtensionError(f"Migration hook {hook_id!r} must return a mapping of project-relative paths.")
        prefix = Path(".project") / "extensions" / extension_id
        for relative, payload in raw.items():
            rel = _safe_relative(str(relative), label="extension migration target")
            try:
                rel.relative_to(prefix)
            except ValueError as exc:
                raise ExtensionError(
                    f"Migration hook {hook_id!r} attempted to modify outside its namespace: {rel.as_posix()}"
                ) from exc
            if isinstance(payload, str):
                data: bytes | None = payload.encode("utf-8")
            elif payload is None or isinstance(payload, bytes):
                data = payload
            else:
                raise ExtensionError(f"Migration hook {hook_id!r} returned unsupported payload type for {rel}")
            key = rel.as_posix()
            if key in targets:
                raise ExtensionError(f"Duplicate extension migration target: {key}")
            targets[key] = data
    extra = sorted(set(current) - set(locked))
    if extra:
        raise ExtensionError(
            "Existing-project upgrade does not implicitly install newly enabled extensions: " + ", ".join(extra)
        )
    return targets


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect and explicitly manage a Project Factory Extension Set")
    sub = parser.add_subparsers(dest="command", required=True)

    inspect = sub.add_parser("inspect")
    inspect.add_argument("manifest", type=Path)

    plan = sub.add_parser("plan")
    plan.add_argument("action", choices=("add", "enable", "disable", "remove"))
    plan.add_argument("--state", required=True, type=Path)
    plan.add_argument("--manifest", type=Path)
    plan.add_argument("--id")
    plan.add_argument("--trust-code", action="store_true")
    plan.add_argument("--out", required=True, type=Path)

    apply = sub.add_parser("apply")
    apply.add_argument("--state", required=True, type=Path)
    apply.add_argument("--plan", required=True, type=Path)
    apply.add_argument("--confirm", required=True)

    listing = sub.add_parser("list")
    listing.add_argument("--state", required=True, type=Path)

    doctor = sub.add_parser("doctor")
    doctor.add_argument("--state", required=True, type=Path)
    doctor.add_argument("--load-trusted-code", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "inspect":
            manifest = load_extension_manifest(args.manifest)
            print(json.dumps({"status": "VALID", "id": manifest.id, "version": manifest.version, "mode": manifest.mode, "manifest_sha256": manifest.manifest_sha256}, indent=2))
            return 0
        if args.command == "plan":
            if args.action == "add":
                if args.manifest is None:
                    raise ExtensionError("plan add requires --manifest")
                plan = plan_add_extension(args.state, args.manifest, trust_code=args.trust_code)
            else:
                if not args.id:
                    raise ExtensionError(f"plan {args.action} requires --id")
                plan = plan_extension_state(args.state, args.id, action=args.action.upper())
            write_extension_plan(args.out, plan)
            print(json.dumps({"status": "DRY_RUN", "plan": str(args.out), "plan_sha256": plan.plan_sha256, "action": plan.action, "extension_id": plan.extension_id}, indent=2))
            return 0
        if args.command == "apply":
            plan = load_extension_plan(args.plan)
            print(json.dumps(apply_extension_plan(args.state, plan, confirm_plan_sha256=args.confirm), indent=2))
            return 0
        if args.command == "list":
            print(json.dumps(load_extension_set(args.state), indent=2))
            return 0
        state = load_extension_set(args.state)
        if args.load_trusted_code:
            runtime = load_extension_runtime(args.state)
            print(json.dumps({"status": "VERIFIED", "state": state, "runtime": runtime.receipt()}, indent=2))
        else:
            for entry in state["extensions"]:
                manifest = load_extension_manifest(_resolve_manifest_reference(args.state, entry["manifest"]))
                if manifest.manifest_sha256 != entry["manifest_sha256"]:
                    raise ExtensionError(f"Extension manifest changed after registration: {manifest.id}")
            print(json.dumps({"status": "METADATA_VERIFIED", "state": state, "trusted_code_loaded": False}, indent=2))
        return 0
    except ExtensionError as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 4


if __name__ == "__main__":
    raise SystemExit(main())


def build_existing_extension_receipt(project_root: Path, runtime: ExtensionRuntime) -> dict[str, Any]:
    """Build a receipt for already materialized extension artifacts without rewriting them."""
    records: list[dict[str, Any]] = []
    root = Path(project_root)
    for artifact in runtime.project_artifacts:
        relative = Path(".project") / "extensions" / artifact.extension_id / artifact.target
        path = root / relative
        if not path.is_file():
            raise ExtensionError(f"Expected extension artifact is missing after migration: {relative.as_posix()}")
        records.append(
            {
                "extension_id": artifact.extension_id,
                "id": artifact.id,
                "kind": artifact.kind,
                "path": relative.as_posix(),
                "sha256": sha256_file(path),
            }
        )
    return {
        "schema_version": "0.1",
        "extensions": [item.receipt() for item in runtime.extensions],
        "artifacts": records,
    }


def assert_upgrade_extension_set(runtime: ExtensionRuntime, locked: Iterable[Mapping[str, Any]]) -> None:
    expected = {str(item.get("id")): dict(item) for item in locked}
    actual = {item.manifest.id: item.receipt() for item in runtime.extensions}
    expected_ids = set(expected)
    actual_ids = set(actual)
    if expected_ids != actual_ids:
        missing = sorted(expected_ids - actual_ids)
        extra = sorted(actual_ids - expected_ids)
        details: list[str] = []
        if missing:
            details.append("missing required extensions: " + ", ".join(missing))
        if extra:
            details.append("new extensions are not implicitly installed during upgrade: " + ", ".join(extra))
        raise ExtensionError("Upgrade Extension Set mismatch: " + "; ".join(details))
    for extension_id, prior in expected.items():
        current = actual[extension_id]
        if str(prior.get("version")) == str(current.get("version")):
            for key in ("contribution_sha256", "distribution_version", "distribution_sha256"):
                prior_value = prior.get(key)
                if prior_value is not None and prior_value != current.get(key):
                    raise ExtensionError(
                        f"Extension {extension_id!r} changed {key} without a version change; refuse same-version code/content drift."
                    )
