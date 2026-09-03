from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml


class HostError(RuntimeError):
    """Raised when an interactive Host contract is invalid or cannot be verified."""


@dataclass(frozen=True)
class HostSpec:
    id: str
    adapter_version: str
    kind: str
    protocol: str
    target_harnesses: tuple[str, ...]
    default: bool
    upstream_contract: dict[str, Any]
    boundaries: dict[str, bool]
    notes: str


DEFAULT_HOST_REGISTRY = Path(__file__).resolve().parent / "registry_data" / "hosts.yaml"
HOST_ROOT = Path(".project/host")
HOST_EVIDENCE_PATH = Path(".project/evidence/host-compatibility.json")
HOST_README_PATH = HOST_ROOT / "README.md"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def load_host_registry(path: Path | None = None) -> dict[str, HostSpec]:
    registry_path = Path(path) if path is not None else DEFAULT_HOST_REGISTRY
    data = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise HostError("Host registry must be a mapping.")
    items = data.get("hosts", [])
    if not isinstance(items, list):
        raise HostError("Host registry hosts must be a list.")
    result: dict[str, HostSpec] = {}
    for item in items:
        if not isinstance(item, dict):
            raise HostError("Host entries must be mappings.")
        boundaries = {str(k): bool(v) for k, v in dict(item.get("boundaries", {})).items()}
        required_false = (
            "owns_extensions",
            "owns_verification",
            "owns_runner",
            "owns_harness_runtime",
            "owns_project_lock",
        )
        if any(boundaries.get(key, True) for key in required_false):
            raise HostError(f"Host {item.get('id')!r} violates the non-ownership contract.")
        spec = HostSpec(
            id=str(item["id"]),
            adapter_version=str(item["adapter_version"]),
            kind=str(item["kind"]),
            protocol=str(item["protocol"]),
            target_harnesses=tuple(str(v) for v in item.get("target_harnesses", [])),
            default=bool(item.get("default", False)),
            upstream_contract=dict(item.get("upstream_contract", {})),
            boundaries=boundaries,
            notes=str(item.get("notes", "")),
        )
        if spec.id in result:
            raise HostError(f"Duplicate Host id: {spec.id}")
        if not spec.target_harnesses:
            raise HostError(f"Host {spec.id!r} must declare at least one target harness.")
        result[spec.id] = spec
    return result


def resolve_hosts(host_ids: Iterable[str] | None, registry: dict[str, HostSpec] | None = None) -> tuple[HostSpec, ...]:
    registry = registry or load_host_registry()
    if host_ids is None:
        ids = tuple(spec.id for spec in registry.values() if spec.default)
    else:
        ids = tuple(host_ids)
    resolved: list[HostSpec] = []
    seen: set[str] = set()
    for host_id in ids:
        if host_id in seen:
            continue
        seen.add(host_id)
        spec = registry.get(host_id)
        if spec is None:
            raise HostError(f"Unknown Host adapter {host_id!r}.")
        resolved.append(spec)
    return tuple(resolved)


def build_host_plan(spec: HostSpec, harness_adapters: dict[str, dict[str, Any]]) -> dict[str, Any]:
    available = set(harness_adapters)
    targets = [item for item in spec.target_harnesses if item in available]
    if not targets:
        raise HostError(
            f"Host {spec.id!r} has no compatible materialized harness. "
            f"Host targets={list(spec.target_harnesses)!r}, project harnesses={sorted(available)!r}."
        )
    contexts = {
        harness_id: str(harness_adapters[harness_id].get("context_file", ""))
        for harness_id in targets
    }
    plan = {
        "schema_version": "0.1",
        "host": {
            "id": spec.id,
            "adapter_version": spec.adapter_version,
            "kind": spec.kind,
            "protocol": spec.protocol,
        },
        "mode": "plan-only",
        "workspace_root": ".",
        "target_harnesses": targets,
        "context_files": contexts,
        "boundaries": dict(spec.boundaries),
        "upstream_contract": dict(spec.upstream_contract),
        "runtime": {
            "status": "UNVERIFIED",
            "host_process_started": False,
            "live_task_executed": False,
        },
        "instructions": [
            "Open the generated project directory as the Host workspace.",
            "Use a Host-detected compatible harness; do not install or replace harnesses from Project Factory.",
            "Treat project.lock.json and .project/evidence as the source of Factory provenance and verification claims.",
        ],
    }
    return plan


def materialize_host_plans(project_root: Path, specs: Iterable[HostSpec], harness_adapters: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    specs = tuple(specs)
    if not specs:
        return None
    root = Path(project_root)
    HOST_ROOT_ABS = root / HOST_ROOT
    HOST_ROOT_ABS.mkdir(parents=True, exist_ok=True)
    plans: dict[str, dict[str, Any]] = {}
    claims: list[dict[str, Any]] = []
    for spec in specs:
        plan = build_host_plan(spec, harness_adapters)
        relative = HOST_ROOT / f"{spec.id}.json"
        path = root / relative
        path.write_text(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        plans[spec.id] = {
            "id": spec.id,
            "adapter_version": spec.adapter_version,
            "protocol": spec.protocol,
            "plan_path": relative.as_posix(),
            "plan_sha256": _sha256_file(path),
            "runtime_verified": False,
            "boundaries": dict(spec.boundaries),
        }
        claims.append({
            "id": f"{spec.id}-workspace-contract",
            "status": "VERIFIED",
            "scope": relative.as_posix(),
            "evidence": {"plan_sha256": _sha256_file(path), "target_harnesses": list(plan["target_harnesses"])},
            "limitation": "Only the Host workspace/harness contract is verified; no GUI process or live Agent task was executed.",
        })
        claims.append({
            "id": f"{spec.id}-runtime",
            "status": "UNVERIFIED",
            "scope": spec.id,
            "evidence": {"runtime_probe": "NOT_RUN"},
            "limitation": "Interactive Host runtime remains outside current execution evidence.",
        })

    readme = """# Interactive Host Plan\n\nThis directory contains **plan-only** Host adapters. Project Factory does not install, launch, configure, or own the Host process.\n\nThe Host is an interchangeable UI entry point over existing Harnesses and the generated project. It does not own Factory Extensions, Verification, Runner lifecycle, Harness runtime, or Project Lock.\n"""
    (root / HOST_README_PATH).write_text(readme, encoding="utf-8")
    report = {
        "schema_version": "0.1",
        "status": "PARTIALLY_VERIFIED",
        "hosts": plans,
        "claims": claims,
        "limitations": [
            "Host plan materialization is verified; live Host runtime is not.",
            "No Host executable, package, setting, or external state is installed or modified by Project Factory.",
        ],
    }
    evidence = root / HOST_EVIDENCE_PATH
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def verify_host_materialization(project_root: Path, host_lock: dict[str, Any] | None) -> dict[str, Any]:
    if not host_lock:
        return {"status": "NOT_CONFIGURED", "failures": [], "runtime_verified": False}
    root = Path(project_root)
    failures: list[str] = []
    hosts = host_lock.get("hosts", {})
    if not isinstance(hosts, dict) or not hosts:
        return {"status": "FAILED", "failures": ["Host lock declares no hosts."], "runtime_verified": False}
    for host_id, item in hosts.items():
        relative = str(item.get("plan_path", ""))
        expected = str(item.get("plan_sha256", ""))
        if not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
            failures.append(f"Unsafe Host plan path for {host_id!r}.")
            continue
        path = root / relative
        if not path.is_file():
            failures.append(f"Missing Host plan: {relative}")
            continue
        actual = _sha256_file(path)
        if expected and actual != expected:
            failures.append(f"Host plan hash mismatch: {relative}")
            continue
        try:
            plan = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            failures.append(f"Invalid Host plan JSON: {relative}")
            continue
        if plan.get("host", {}).get("id") != host_id:
            failures.append(f"Host plan id mismatch: {relative}")
        if any(bool(plan.get("boundaries", {}).get(key, True)) for key in (
            "owns_extensions", "owns_verification", "owns_runner", "owns_harness_runtime", "owns_project_lock"
        )):
            failures.append(f"Host plan violates non-ownership boundary: {relative}")
    evidence = root / HOST_EVIDENCE_PATH
    if not evidence.is_file():
        failures.append(f"Missing Host evidence: {HOST_EVIDENCE_PATH.as_posix()}")
    readme = root / HOST_README_PATH
    if not readme.is_file():
        failures.append(f"Missing Host README: {HOST_README_PATH.as_posix()}")
    return {
        "status": "FAILED" if failures else "PARTIALLY_VERIFIED",
        "failures": failures,
        "runtime_verified": False,
        "hosts": sorted(hosts),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect Project Factory interactive Host contracts")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("catalog", help="List registered Host adapters")
    verify = sub.add_parser("verify", help="Verify Host materialization from a generated project")
    verify.add_argument("project_root", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "catalog":
            registry = load_host_registry()
            print(json.dumps({key: asdict(value) for key, value in registry.items()}, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        lock = json.loads((args.project_root / "project.lock.json").read_text(encoding="utf-8"))
        result = verify_host_materialization(args.project_root, lock.get("host_integration"))
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if result["status"] != "FAILED" else 1
    except (HostError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
