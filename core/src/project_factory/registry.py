from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml


class RegistryError(RuntimeError):
    """Raised when registry data is invalid or resolution is ambiguous."""


@dataclass(frozen=True)
class CapabilitySpec:
    id: str
    version: str
    description: str


@dataclass(frozen=True)
class ProviderSpec:
    id: str
    version: str
    capability: str
    executable: str
    version_args: tuple[str, ...]
    version_regex: str
    tested_versions: tuple[str, ...]
    supported_versions: tuple[str, ...]
    integration: str
    upstream_source_modified: bool


@dataclass(frozen=True)
class ProfileSpec:
    id: str
    version: str
    priority: int
    match: dict[str, tuple[str, ...]]
    capabilities: tuple[str, ...]
    provider_preferences: dict[str, tuple[str, ...]]
    scaffold_recipe: str
    verification_recipe: str
    materialization: str
    # O1: declarative car-type family. The SINGLE SOURCE OF TRUTH for the
    # selection advisor's overlap grouping (web/service/library/...). Profiles
    # sharing a work_product kind must share a family; the advisor never
    # hardcodes the kind->family mapping anymore.
    family: str = ""
    # E2: optional sub-type within a family (e.g. the original data/AI car type
    # before the 14 profiles were folded into `family: data`). Advisor-agnostic;
    # purely documentation/branching metadata for the GUI and scaffolder.
    intent: str = ""


@dataclass(frozen=True)
class FormulaSpec:
    id: str
    version: str
    priority: int
    applies_to: tuple[str, ...]
    adapter: str
    description: str


@dataclass(frozen=True)
class PolicySpec:
    id: str
    version: str
    priority: int
    applies_to: tuple[str, ...]
    rules: dict[str, Any]
    description: str


@dataclass(frozen=True)
class ProviderRuntime:
    spec: ProviderSpec
    version: str
    executable_path: str
    version_status: str = "SUPPORTED"  # T23: SUPPORTED / COMPATIBLE (detected, never blocks)


@dataclass(frozen=True)
class Registry:
    capabilities: dict[str, CapabilitySpec]
    providers: dict[str, ProviderSpec]
    profiles: dict[str, ProfileSpec]
    formulas: dict[str, FormulaSpec]
    policies: dict[str, PolicySpec]


DEFAULT_REGISTRY_DIR = Path(__file__).resolve().parent / "registry_data"


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RegistryError(f"Registry file must contain a mapping: {path}")
    return data


def _unique_by_id(items: Iterable[Any], *, kind: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for item in items:
        if item.id in out:
            raise RegistryError(f"Duplicate {kind} id: {item.id}")
        out[item.id] = item
    return out


def _user_warehouse_dir() -> Path | None:
    flag = os.environ.get("PROJECT_FACTORY_LOAD_USER_WAREHOUSE", "").strip().casefold()
    if flag in {"0", "false", "no"}:
        return None
    explicit = os.environ.get("PROJECT_FACTORY_USER_WAREHOUSE", "").strip()
    if explicit:
        return Path(explicit)
    if flag in {"1", "true", "yes"}:
        local = os.environ.get("LOCALAPPDATA") or str(Path.home())
        return Path(local) / "ProjectFactory" / "user_warehouse"
    return None


def load_registry(registry_dir: Path | None = None, extension_runtime: Any | None = None) -> Registry:
    root = Path(registry_dir or DEFAULT_REGISTRY_DIR)
    capability_doc = _load_yaml(root / "capabilities.yaml")
    provider_doc = _load_yaml(root / "providers.yaml")
    profile_doc = _load_yaml(root / "profiles.yaml")
    formula_doc = _load_yaml(root / "formulas.yaml")
    policy_doc = _load_yaml(root / "policies.yaml")

    user_root = _user_warehouse_dir()
    if user_root is not None:
        for filename, doc, key in (
            ("capabilities.yaml", capability_doc, "capabilities"),
            ("providers.yaml", provider_doc, "providers"),
            ("profiles.yaml", profile_doc, "profiles"),
            ("formulas.yaml", formula_doc, "formulas"),
            ("policies.yaml", policy_doc, "policies"),
        ):
            extra_path = user_root / filename
            if extra_path.is_file():
                try:
                    extra_doc = _load_yaml(extra_path)
                except (OSError, yaml.YAMLError, RegistryError):
                    continue
                extra_items = extra_doc.get(key, [])
                if isinstance(extra_items, list) and extra_items:
                    existing = doc.get(key, [])
                    if isinstance(existing, list):
                        doc[key] = [*existing, *extra_items]

    if extension_runtime is not None:
        docs = {
            "capabilities": capability_doc,
            "providers": provider_doc,
            "profiles": profile_doc,
            "formulas": formula_doc,
            "policies": policy_doc,
        }
        contributions = getattr(extension_runtime, "registry_contributions", {})
        for kind, doc in docs.items():
            extra = list(contributions.get(kind, []))
            if extra:
                existing = doc.get(kind, [])
                if not isinstance(existing, list):
                    raise RegistryError(f"Core registry section {kind!r} must be a list.")
                doc[kind] = [*existing, *extra]

    capabilities = _unique_by_id(
        (
            CapabilitySpec(
                id=str(item["id"]),
                version=str(item["version"]),
                description=str(item.get("description", "")),
            )
            for item in capability_doc.get("capabilities", [])
        ),
        kind="capability",
    )

    providers = _unique_by_id(
        (
            ProviderSpec(
                id=str(item["id"]),
                version=str(item["version"]),
                capability=str(item["capability"]),
                executable=str(item["executable"]),
                version_args=tuple(str(value) for value in item.get("version_args", [])),
                version_regex=str(item["version_regex"]),
                tested_versions=tuple(str(value) for value in item.get("tested_versions", [])),
                supported_versions=tuple(str(value) for value in item.get("supported_versions", item.get("tested_versions", []))),
                integration=str(item.get("integration", "public-cli")),
                upstream_source_modified=bool(item.get("upstream_source_modified", False)),
            )
            for item in provider_doc.get("providers", [])
        ),
        kind="provider",
    )

    profiles = _unique_by_id(
        (
            ProfileSpec(
                id=str(item["id"]),
                version=str(item["version"]),
                priority=int(item.get("priority", 0)),
                match={key: tuple(str(value) for value in values) for key, values in item.get("match", {}).items()},
                capabilities=tuple(str(value) for value in item.get("capabilities", [])),
                provider_preferences={
                    key: tuple(str(value) for value in values)
                    for key, values in item.get("provider_preferences", {}).items()
                },
                scaffold_recipe=str(item["scaffold_recipe"]),
                verification_recipe=str(item["verification_recipe"]),
                materialization=str(item.get("materialization", "minimal")),
                family=str(item.get("family", "")),
                intent=str(item.get("intent", "")),
            )
            for item in profile_doc.get("profiles", [])
        ),
        kind="profile",
    )

    formulas = _unique_by_id(
        (
            FormulaSpec(
                id=str(item["id"]),
                version=str(item["version"]),
                priority=int(item.get("priority", 0)),
                applies_to=tuple(str(value) for value in item.get("applies_to", ["*"])),
                adapter=str(item["adapter"]),
                description=str(item.get("description", "")),
            )
            for item in formula_doc.get("formulas", [])
        ),
        kind="formula",
    )

    policies = _unique_by_id(
        (
            PolicySpec(
                id=str(item["id"]),
                version=str(item["version"]),
                priority=int(item.get("priority", 0)),
                applies_to=tuple(str(value) for value in item.get("applies_to", ["*"])),
                rules=dict(item.get("rules", {})),
                description=str(item.get("description", "")),
            )
            for item in policy_doc.get("policies", [])
        ),
        kind="policy",
    )

    if not formulas:
        raise RegistryError("Registry must declare at least one Formula.")
    if not policies:
        raise RegistryError("Registry must declare at least one Policy.")

    for formula in formulas.values():
        if not formula.applies_to:
            raise RegistryError(f"Formula {formula.id!r} must declare applies_to.")
        if not formula.adapter:
            raise RegistryError(f"Formula {formula.id!r} must declare a trusted adapter id.")

    from .policies import PolicyError, validate_policy_rules
    for policy in policies.values():
        if not policy.applies_to:
            raise RegistryError(f"Policy {policy.id!r} must declare applies_to.")
        try:
            validate_policy_rules(policy.rules)
        except PolicyError as exc:
            raise RegistryError(f"Policy {policy.id!r} is invalid: {exc}") from exc

    for provider in providers.values():
        if provider.capability not in capabilities:
            raise RegistryError(
                f"Provider {provider.id!r} references unknown capability {provider.capability!r}."
            )
        if not provider.tested_versions:
            raise RegistryError(f"Provider {provider.id!r} has no tested_versions.")
        # T23: supported_versions may now be broader than tested_versions (e.g. a
        # version range). Generation is no longer blocked on version, so the previous
        # "supported must also be tested" invariant is intentionally dropped.

    for profile in profiles.values():
        if not profile.capabilities:
            raise RegistryError(f"Profile {profile.id!r} must request at least one capability.")
        for capability in profile.capabilities:
            if capability not in capabilities:
                raise RegistryError(
                    f"Profile {profile.id!r} references unknown capability {capability!r}."
                )
            preferences = profile.provider_preferences.get(capability, ())
            if not preferences:
                raise RegistryError(
                    f"Profile {profile.id!r} has no provider preference for {capability!r}."
                )
            for provider_id in preferences:
                provider = providers.get(provider_id)
                if provider is None:
                    raise RegistryError(
                        f"Profile {profile.id!r} references unknown provider {provider_id!r}."
                    )
                if provider.capability != capability:
                    raise RegistryError(
                        f"Provider {provider_id!r} does not implement {capability!r}."
                    )

    return Registry(capabilities=capabilities, providers=providers, profiles=profiles, formulas=formulas, policies=policies)


def _profile_matches(profile: ProfileSpec, blueprint: dict[str, Any]) -> bool:
    products = {str(item.get("kind")) for item in blueprint.get("work_products", [])}
    technologies = {str(item) for item in blueprint.get("technology", {}).get("required", [])}
    rules = profile.match

    any_products = set(rules.get("work_products_any", ()))
    if any_products and products.isdisjoint(any_products):
        return False

    all_products = set(rules.get("work_products_all", ()))
    if all_products and not all_products.issubset(products):
        return False

    any_technology = set(rules.get("technology_required_any", ()))
    if any_technology and technologies.isdisjoint(any_technology):
        return False

    all_technology = set(rules.get("technology_required_all", ()))
    if all_technology and not all_technology.issubset(technologies):
        return False

    return True


def select_profile(blueprint: dict[str, Any], registry: Registry | None = None) -> ProfileSpec:
    registry = registry or load_registry()
    matches = [profile for profile in registry.profiles.values() if _profile_matches(profile, blueprint)]
    if not matches:
        raise RegistryError("No registered profile matches this Blueprint.")
    matches.sort(key=lambda item: item.priority, reverse=True)
    best_priority = matches[0].priority
    best = [item for item in matches if item.priority == best_priority]
    if len(best) != 1:
        ids = ", ".join(sorted(item.id for item in best))
        raise RegistryError(f"Ambiguous profile resolution at priority {best_priority}: {ids}")
    return best[0]


def inspect_provider(spec: ProviderSpec) -> ProviderRuntime:
    from .tools import resolve_executable

    executable = resolve_executable(spec.executable)
    if not executable:
        raise RegistryError(
            f"Provider {spec.id!r} is unavailable: executable {spec.executable!r} was not found in PATH."
        )
    try:
        completed = subprocess.run(
            [executable, *spec.version_args],
            text=True,
            capture_output=True,
            check=False,
            timeout=15,
        )
    except subprocess.TimeoutExpired as exc:
        raise RegistryError(
            f"Provider {spec.id!r} version probe timed out after 15s."
        ) from exc
    if completed.returncode != 0:
        raise RegistryError(
            f"Provider {spec.id!r} version probe failed with exit {completed.returncode}: "
            f"{completed.stdout}{completed.stderr}"
        )
    output = (completed.stdout.strip() or completed.stderr.strip()).strip()
    match = re.search(spec.version_regex, output)
    if not match:
        raise RegistryError(f"Could not parse {spec.id} version from: {output!r}")
    version = match.group(1)
    # T23: the version gate is removed. The factory DETECTS and REPORTS the local
    # tool version but never blocks generation on it — developers may use their own
    # toolchain (any version), managing versions and combinations themselves.
    # Only a missing/unparseable tool still blocks (handled above).
    if version in spec.tested_versions or version in spec.supported_versions:
        status = "SUPPORTED"
    else:
        status = "COMPATIBLE"
    return ProviderRuntime(
        spec=spec, version=version, executable_path=executable, version_status=status
    )


def resolve_providers(
    profile: ProfileSpec,
    registry: Registry | None = None,
) -> dict[str, ProviderRuntime]:
    registry = registry or load_registry()
    resolved: dict[str, ProviderRuntime] = {}
    for capability in profile.capabilities:
        failures: list[str] = []
        for provider_id in profile.provider_preferences[capability]:
            spec = registry.providers[provider_id]
            try:
                resolved[capability] = inspect_provider(spec)
                break
            except RegistryError as exc:
                failures.append(str(exc))
        if capability not in resolved:
            joined = " | ".join(failures) or "no provider candidates"
            raise RegistryError(f"No usable provider for capability {capability!r}: {joined}")
    return resolved
