from __future__ import annotations

import argparse
import importlib.metadata as metadata
import json
import platform
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from .factory import FACTORY_STAGE, FACTORY_VERSION, FactoryError, generate_project, restore_verify_project_zip
from .harness import HarnessError, load_harness_registry
from .host import HostError, load_host_registry
from .process import ProcessIntegrationError, load_process_registry
from .registry import RegistryError, inspect_provider, load_registry
from .runner import RunnerError, load_runner_registry, probe_runner_runtime
from .validator import DEFAULT_BLUEPRINT_SCHEMA, DEFAULT_META_SCHEMA


class ProductError(RuntimeError):
    """Raised when a product-facing self-check cannot be completed safely."""


def _distribution_mode() -> dict[str, Any]:
    try:
        dist = metadata.distribution("project-factory-blueprint-kernel")
        return {
            "status": "INSTALLED_DISTRIBUTION",
            "name": dist.metadata.get("Name", "project-factory-blueprint-kernel"),
            "version": dist.version,
        }
    except metadata.PackageNotFoundError:
        return {
            "status": "SOURCE_TREE",
            "name": "project-factory-blueprint-kernel",
            "version": FACTORY_VERSION,
        }


def _optional_binary(executable: str) -> dict[str, Any]:
    resolved = shutil.which(executable)
    return {
        "executable": executable,
        "status": "AVAILABLE_UNVERIFIED" if resolved else "UNAVAILABLE",
        "path": resolved,
        "runtime_verified": False,
    }


def _registry_health() -> dict[str, Any]:
    try:
        registry = load_registry()
        harnesses = load_harness_registry()
        hosts = load_host_registry()
        processes = load_process_registry()
        runners = load_runner_registry()
    except (RegistryError, HarnessError, HostError, ProcessIntegrationError, RunnerError, OSError, ValueError) as exc:
        return {"status": "FAILED", "error": str(exc)}
    return {
        "status": "PASS",
        "counts": {
            "capabilities": len(registry.capabilities),
            "providers": len(registry.providers),
            "profiles": len(registry.profiles),
            "formulas": len(registry.formulas),
            "policies": len(registry.policies),
            "harnesses": len(harnesses),
            "hosts": len(hosts),
            "process_integrations": len(processes),
            "runners": len(runners),
        },
    }


def _schema_health() -> dict[str, Any]:
    paths = [DEFAULT_BLUEPRINT_SCHEMA, DEFAULT_META_SCHEMA]
    missing = [str(path) for path in paths if not path.is_file()]
    return {
        "status": "PASS" if not missing else "FAILED",
        "files": [str(path) for path in paths],
        "missing": missing,
    }


def _provider_health() -> tuple[dict[str, Any], dict[str, bool]]:
    registry = load_registry()
    providers: dict[str, Any] = {}
    usable: dict[str, bool] = {}
    for provider_id, spec in sorted(registry.providers.items()):
        try:
            runtime = inspect_provider(spec)
            providers[provider_id] = {
                "status": "SUPPORTED",
                "version": runtime.version,
                "executable": runtime.executable_path,
                "capability": spec.capability,
            }
            usable[provider_id] = True
        except RegistryError as exc:
            providers[provider_id] = {
                "status": "UNAVAILABLE_OR_UNSUPPORTED",
                "capability": spec.capability,
                "error": str(exc),
            }
            usable[provider_id] = False
    return providers, usable


def _profile_health(provider_usable: dict[str, bool]) -> dict[str, Any]:
    registry = load_registry()
    result: dict[str, Any] = {}
    for profile_id, profile in sorted(registry.profiles.items()):
        capability_state: dict[str, Any] = {}
        ready = True
        for capability in profile.capabilities:
            preferences = list(profile.provider_preferences.get(capability, ()))
            selected = next((provider for provider in preferences if provider_usable.get(provider, False)), None)
            capability_state[capability] = {
                "provider_preferences": preferences,
                "selected_supported_provider": selected,
            }
            if selected is None:
                ready = False
        result[profile_id] = {
            "status": "READY" if ready else "BLOCKED",
            "capabilities": capability_state,
        }
    return result


def _runner_health() -> dict[str, Any]:
    result: dict[str, Any] = {}
    try:
        registry = load_runner_registry()
        for runner_id, spec in sorted(registry.items()):
            probe = probe_runner_runtime(spec)
            result[runner_id] = probe
    except (RunnerError, OSError, ValueError) as exc:
        return {"registry": {"status": "FAILED", "error": str(exc)}}
    return result


def _deep_smoke() -> dict[str, Any]:
    requirement = "做一个 Python 命令行工具，用于输出项目自检信息。不能覆盖原始文件。"
    try:
        with tempfile.TemporaryDirectory(prefix="project-factory-doctor-") as td:
            output = Path(td) / "out"
            result = generate_project(requirement, "doctor-smoke-cli", output)
            restored = restore_verify_project_zip(result.project_zip)
            return {
                "status": "PASS",
                "generation_status": result.verification["status"],
                "restore_status": restored["status"],
                "profile": result.profile.profile_id,
                "persistent_output": False,
            }
    except (FactoryError, OSError, ValueError) as exc:
        return {"status": "FAILED", "error": str(exc), "persistent_output": False}


def doctor(*, deep: bool = False) -> dict[str, Any]:
    registry = _registry_health()
    schemas = _schema_health()
    providers: dict[str, Any] = {}
    profiles: dict[str, Any] = {}
    provider_usable: dict[str, bool] = {}
    if registry.get("status") == "PASS":
        try:
            providers, provider_usable = _provider_health()
            profiles = _profile_health(provider_usable)
        except (RegistryError, OSError, ValueError) as exc:
            registry = {"status": "FAILED", "error": str(exc)}

    harnesses: dict[str, Any] = {}
    try:
        for harness_id, spec in sorted(load_harness_registry().items()):
            harnesses[harness_id] = _optional_binary(spec.executable)
    except (HarnessError, OSError, ValueError) as exc:
        harnesses = {"registry": {"status": "FAILED", "error": str(exc)}}

    process_integrations: dict[str, Any] = {}
    try:
        for process_id, spec in sorted(load_process_registry().items()):
            process_integrations[process_id] = _optional_binary(spec.executable)
    except (ProcessIntegrationError, OSError, ValueError) as exc:
        process_integrations = {"registry": {"status": "FAILED", "error": str(exc)}}

    hosts: dict[str, Any] = {}
    try:
        for host_id, spec in sorted(load_host_registry().items()):
            hosts[host_id] = {
                "status": "CONTRACT_ONLY",
                "protocol": spec.protocol,
                "runtime_verified": False,
            }
    except (HostError, OSError, ValueError) as exc:
        hosts = {"registry": {"status": "FAILED", "error": str(exc)}}

    deep_report = _deep_smoke() if deep else {"status": "NOT_RUN"}
    blocked_profiles = sorted(profile_id for profile_id, value in profiles.items() if value.get("status") != "READY")
    ready_profiles = sorted(profile_id for profile_id, value in profiles.items() if value.get("status") == "READY")
    hard_failures = []
    if registry.get("status") != "PASS":
        hard_failures.append("registry")
    if schemas.get("status") != "PASS":
        hard_failures.append("schemas")
    if not ready_profiles:
        hard_failures.append("no-ready-profile")
    if deep and deep_report.get("status") != "PASS":
        hard_failures.append("deep-smoke")

    warnings: list[str] = []
    if blocked_profiles:
        warnings.append("Some project profiles are unavailable in the current tool environment: " + ", ".join(blocked_profiles))
    unavailable_optional = []
    for group_name, group in (("harness", harnesses), ("process", process_integrations), ("runner", _runner_health())):
        for item_id, value in group.items():
            if isinstance(value, dict) and value.get("status") in {"UNAVAILABLE", "UNAVAILABLE_OR_UNSUPPORTED"}:
                unavailable_optional.append(f"{group_name}:{item_id}")
    if unavailable_optional:
        warnings.append("Optional external runtimes are unavailable: " + ", ".join(sorted(unavailable_optional)))

    status = "BLOCKED" if hard_failures else ("READY_WITH_WARNINGS" if warnings else "READY")
    return {
        "schema_version": "0.1",
        "status": status,
        "factory": {"version": FACTORY_VERSION, "stage": FACTORY_STAGE},
        "distribution": _distribution_mode(),
        "environment": {
            "python": platform.python_version(),
            "python_executable": sys.executable,
            "platform": platform.platform(),
        },
        "registry": registry,
        "schemas": schemas,
        "providers": providers,
        "profiles": profiles,
        "harnesses": harnesses,
        "process_integrations": process_integrations,
        "hosts": hosts,
        "runners": _runner_health(),
        "deep_smoke": deep_report,
        "ready_profiles": ready_profiles,
        "hard_failures": hard_failures,
        "warnings": warnings,
    }


def bootstrap(*, deep: bool = False) -> dict[str, Any]:
    report = doctor(deep=deep)
    ready = report["status"] != "BLOCKED"
    return {
        "schema_version": "0.1",
        "status": "READY" if ready else "BLOCKED",
        "factory": report["factory"],
        "doctor_status": report["status"],
        "persistent_state_created": False,
        "quickstart": {
            "status": "project-factory status --deep",
            "new": "project-factory new my-project '做一个 Python 命令行工具。'",
            "check": "project-factory check ./out/my-project",
            "verify": "project-factory verify ./out/my-project.zip",
            "doctor": "project-factory doctor --deep",
            "generate": "project-factory generate --name my-project --output-dir ./out '做一个 Python 命令行工具。'",
            "restore_verify": "project-factory restore-verify ./out/my-project.zip",
        },
        "ready_profiles": report["ready_profiles"],
        "warnings": report["warnings"],
        "hard_failures": report["hard_failures"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Project Factory product readiness commands")
    sub = parser.add_subparsers(dest="command", required=True)
    doctor_p = sub.add_parser("doctor", help="Read-only readiness and dependency diagnosis")
    doctor_p.add_argument("--deep", action="store_true", help="Generate and restore-verify a temporary smoke project")
    bootstrap_p = sub.add_parser("bootstrap", help="First-run readiness check and quickstart without persistent state")
    bootstrap_p.add_argument("--deep", action="store_true", help="Include temporary end-to-end smoke generation")
    args = parser.parse_args(argv)
    result = doctor(deep=args.deep) if args.command == "doctor" else bootstrap(deep=args.deep)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] != "BLOCKED" else 4


if __name__ == "__main__":
    raise SystemExit(main())
