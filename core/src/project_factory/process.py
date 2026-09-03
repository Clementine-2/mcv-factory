from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml


class ProcessIntegrationError(RuntimeError):
    """Raised when a process integration cannot be planned or executed safely."""


@dataclass(frozen=True)
class ProcessIntegrationSpec:
    id: str
    adapter_version: str
    upstream_version: str
    executable: str
    supported_harnesses: tuple[str, ...]
    default_harness: str
    script_type: str
    agent_context_extension: bool
    upstream_source_modified: bool
    runtime_verified: bool
    upstream_contract: dict[str, Any]
    notes: str


DEFAULT_PROCESS_REGISTRY = Path(__file__).resolve().parent / "registry_data" / "process_integrations.yaml"
PROCESS_PLAN_PATH = Path(".project/process/spec-kit-plan.json")
PROCESS_INSTALL_PATH = Path(".project/process/INSTALL.md")
PROCESS_EVIDENCE_PATH = Path(".project/evidence/process-integration.json")


def load_process_registry(path: Path | None = None) -> dict[str, ProcessIntegrationSpec]:
    registry_path = Path(path) if path is not None else DEFAULT_PROCESS_REGISTRY
    data = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ProcessIntegrationError("Process integration registry must be a mapping.")
    items = data.get("process_integrations", [])
    if not isinstance(items, list) or not items:
        raise ProcessIntegrationError("Process integration registry must declare at least one integration.")
    result: dict[str, ProcessIntegrationSpec] = {}
    for item in items:
        if not isinstance(item, dict):
            raise ProcessIntegrationError("Process integration entries must be mappings.")
        spec = ProcessIntegrationSpec(
            id=str(item["id"]),
            adapter_version=str(item["adapter_version"]),
            upstream_version=str(item["upstream_version"]),
            executable=str(item["executable"]),
            supported_harnesses=tuple(str(value) for value in item.get("supported_harnesses", [])),
            default_harness=str(item["default_harness"]),
            script_type=str(item.get("script_type", "py")),
            agent_context_extension=bool(item.get("agent_context_extension", False)),
            upstream_source_modified=bool(item.get("upstream_source_modified", False)),
            runtime_verified=bool(item.get("runtime_verified", False)),
            upstream_contract=dict(item.get("upstream_contract", {})),
            notes=str(item.get("notes", "")),
        )
        if spec.id in result:
            raise ProcessIntegrationError(f"Duplicate process integration id: {spec.id}")
        if not spec.supported_harnesses:
            raise ProcessIntegrationError(f"Process integration {spec.id!r} has no supported harnesses.")
        if spec.default_harness not in spec.supported_harnesses:
            raise ProcessIntegrationError(f"Process integration {spec.id!r} has invalid default_harness.")
        result[spec.id] = spec
    return result


def resolve_process_integration(integration_id: str | None) -> ProcessIntegrationSpec | None:
    if integration_id is None:
        return None
    registry = load_process_registry()
    spec = registry.get(integration_id)
    if spec is None:
        raise ProcessIntegrationError(f"Unknown process integration {integration_id!r}.")
    return spec


def build_process_plan(spec: ProcessIntegrationSpec, harness_ids: Iterable[str]) -> dict[str, Any]:
    harnesses = tuple(dict.fromkeys(str(value) for value in harness_ids))
    if not harnesses:
        raise ProcessIntegrationError("Spec Kit plan requires at least one harness integration.")
    unsupported = [item for item in harnesses if item not in spec.supported_harnesses]
    if unsupported:
        raise ProcessIntegrationError(
            f"Process integration {spec.id!r} does not support harnesses: {', '.join(unsupported)}"
        )
    default = spec.default_harness if spec.default_harness in harnesses else harnesses[0]
    ordered = (default,) + tuple(item for item in harnesses if item != default)
    commands: list[list[str]] = [
        [spec.executable, "init", "--here", "--integration", default, "--script", spec.script_type]
    ]
    for harness_id in ordered[1:]:
        commands.append(
            [spec.executable, "integration", "install", harness_id, "--script", spec.script_type]
        )
    commands.append([spec.executable, "integration", "status"])
    return {
        "schema_version": "0.1",
        "provider": {
            "id": spec.id,
            "adapter_version": spec.adapter_version,
            "upstream_version": spec.upstream_version,
            "upstream_source_modified": spec.upstream_source_modified,
        },
        "default_harness": default,
        "target_harnesses": list(ordered),
        "commands": commands,
        "agent_context_extension": spec.agent_context_extension,
        "context_ownership": "project-factory",
        "upstream_contract": spec.upstream_contract,
        "status": "PLANNED_NOT_INSTALLED",
        "limitations": [
            "The plan is derived from the Spec Kit v1.0.1 public integration contract.",
            "The Factory does not claim the real Spec Kit CLI executed unless execution evidence is present.",
            "The Spec Kit agent-context extension is intentionally not installed because Project Factory owns AGENTS.md/CLAUDE.md.",
        ],
    }


def materialize_process_plan(project_root: Path, plan: dict[str, Any]) -> dict[str, Any]:
    project_root = Path(project_root)
    plan_path = project_root / PROCESS_PLAN_PATH
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    install_lines = [
        "# Optional Spec Kit Process Integration",
        "",
        "This project is usable without Spec Kit. The commands below install the optional process layer.",
        "Project Factory owns `AGENTS.md` and `CLAUDE.md`; do not add the Spec Kit `agent-context` extension unless ownership is explicitly changed.",
        "",
        f"Pinned upstream contract: Spec Kit {plan['provider']['upstream_version']}",
        "",
        "## Planned commands",
        "",
    ]
    for command in plan["commands"]:
        install_lines.append("```bash")
        install_lines.append(" ".join(command))
        install_lines.append("```")
        install_lines.append("")
    install_lines.extend(
        [
            "## Verification boundary",
            "",
            "A plan file is not proof that Spec Kit was installed. Check `.project/evidence/process-integration.json` and `.specify/integration.json` after a real installation.",
            "",
        ]
    )
    install_path = project_root / PROCESS_INSTALL_PATH
    install_path.write_text("\n".join(install_lines), encoding="utf-8")
    report = {
        "schema_version": "0.1",
        "status": "PLANNED_NOT_INSTALLED",
        "provider": plan["provider"],
        "plan_path": PROCESS_PLAN_PATH.as_posix(),
        "runtime_verified": False,
        "claims": [
            {
                "id": "spec-kit-command-plan",
                "status": "VERIFIED",
                "scope": PROCESS_PLAN_PATH.as_posix(),
                "limitation": "Command construction is verified against the pinned public contract; real CLI execution is not implied.",
            },
            {
                "id": "spec-kit-runtime-install",
                "status": "UNVERIFIED",
                "scope": spec_scope(plan),
                "limitation": "No real Spec Kit runtime evidence is present in plan-only mode.",
            },
        ],
    }
    evidence_path = project_root / PROCESS_EVIDENCE_PATH
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def spec_scope(plan: Mapping[str, Any]) -> str:
    provider = plan.get("provider", {})
    return f"{provider.get('id', 'process')}@{provider.get('upstream_version', 'unknown')}"


def _portable_result(result: subprocess.CompletedProcess[str], display_argv: list[str]) -> dict[str, Any]:
    return {
        "argv": list(display_argv),
        "returncode": result.returncode,
        "stdout": result.stdout[-4000:],
        "stderr": result.stderr[-4000:],
    }


def _detect_specify_version(executable: str, *, env: Mapping[str, str] | None = None) -> str:
    resolved = shutil.which(executable, path=(env or os.environ).get("PATH"))
    if not resolved:
        raise ProcessIntegrationError(f"Required process provider executable {executable!r} is not available.")
    try:
        result = subprocess.run(
            [resolved, "version"],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=30,
            env=dict(env or os.environ),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ProcessIntegrationError(
            f"Process provider {executable!r} version probe timed out after 30s."
        ) from exc
    if result.returncode != 0:
        raise ProcessIntegrationError(f"Unable to read {executable!r} version: {result.stderr.strip()}")
    match = re.search(r"(\d+\.\d+\.\d+)", result.stdout + "\n" + result.stderr)
    if not match:
        raise ProcessIntegrationError(f"Unable to parse {executable!r} version output.")
    return match.group(1)


def execute_process_plan(
    project_root: Path,
    spec: ProcessIntegrationSpec,
    plan: dict[str, Any],
    *,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Execute the trusted Spec Kit command plan.

    This function never shells out through a string. It only accepts a plan produced
    by build_process_plan() and validates the pinned upstream version before mutation.
    Callers should execute inside a staging project so a failure cannot corrupt the
    final generated output.
    """
    if spec.id != "spec-kit" or spec.adapter_version != "0.1":
        raise ProcessIntegrationError("No trusted process adapter is registered for this integration.")
    version = _detect_specify_version(spec.executable, env=env)
    if version != spec.upstream_version:
        raise ProcessIntegrationError(
            f"Process provider version {version!r} is not the pinned supported contract version {spec.upstream_version!r}."
        )
    results: list[dict[str, Any]] = []
    run_env = dict(env or os.environ)
    for command in plan["commands"]:
        if not isinstance(command, list) or not command or command[0] != spec.executable:
            raise ProcessIntegrationError("Process plan contains an untrusted command shape.")
        resolved = shutil.which(spec.executable, path=run_env.get("PATH"))
        if not resolved:
            raise ProcessIntegrationError(f"Process provider executable {spec.executable!r} disappeared before execution.")
        argv = [resolved, *command[1:]]
        try:
            result = subprocess.run(
                argv,
                cwd=project_root,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=120,
                env=run_env,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ProcessIntegrationError(
                f"Process integration command timed out after 120s: {' '.join(command)}"
            ) from exc
        results.append(_portable_result(result, command))
        if result.returncode != 0:
            raise ProcessIntegrationError(
                f"Process integration command failed ({result.returncode}): {' '.join(command)}\n{result.stderr.strip()}"
            )

    integration_json = project_root / ".specify" / "integration.json"
    if not integration_json.is_file():
        raise ProcessIntegrationError("Spec Kit execution did not produce .specify/integration.json.")
    state = json.loads(integration_json.read_text(encoding="utf-8"))
    installed = state.get("installed_integrations", [])
    expected = list(plan["target_harnesses"])
    missing = [item for item in expected if item not in installed]
    if missing:
        raise ProcessIntegrationError(
            "Spec Kit integration state does not contain expected harnesses: " + ", ".join(missing)
        )

    skills_dirs = {
        "codex": project_root / ".agents" / "skills",
        "claude": project_root / ".claude" / "skills",
    }
    missing_dirs = [key for key in expected if key in skills_dirs and not skills_dirs[key].is_dir()]
    if missing_dirs:
        raise ProcessIntegrationError(
            "Spec Kit execution did not materialize expected skills directories: " + ", ".join(missing_dirs)
        )

    report = {
        "schema_version": "0.1",
        "status": "INSTALLED_CONTRACT_VERIFIED",
        "provider": {
            "id": spec.id,
            "adapter_version": spec.adapter_version,
            "upstream_version": version,
            "upstream_source_modified": spec.upstream_source_modified,
        },
        "runtime_verified": True,
        "installed_harnesses": expected,
        "integration_state": ".specify/integration.json",
        "commands": results,
        "claims": [
            {"id": "spec-kit-runtime-install", "status": "VERIFIED", "scope": spec_scope(plan)},
            {"id": "spec-kit-integration-state", "status": "VERIFIED", "scope": ".specify/integration.json"},
            {"id": "spec-kit-harness-skills", "status": "VERIFIED", "scope": expected},
        ],
        "limitations": [
            "This verifies installation artifacts and command success, not the semantic quality of a live coding-agent session."
        ],
    }
    evidence_path = project_root / PROCESS_EVIDENCE_PATH
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def verify_process_materialization(project_root: Path, process_lock: dict[str, Any] | None) -> dict[str, Any]:
    if not process_lock:
        return {"status": "NOT_CONFIGURED", "failures": [], "runtime_verified": False}
    project_root = Path(project_root)
    failures: list[str] = []
    plan_path = project_root / PROCESS_PLAN_PATH
    evidence_path = project_root / PROCESS_EVIDENCE_PATH
    if not plan_path.is_file():
        failures.append(f"Missing process plan: {PROCESS_PLAN_PATH.as_posix()}")
        plan: dict[str, Any] = {}
    else:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if not evidence_path.is_file():
        failures.append(f"Missing process evidence: {PROCESS_EVIDENCE_PATH.as_posix()}")
        evidence: dict[str, Any] = {}
    else:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))

    locked_provider = process_lock.get("provider", {})
    plan_provider = plan.get("provider", {})
    for key in ("id", "adapter_version", "upstream_version"):
        if locked_provider.get(key) != plan_provider.get(key):
            failures.append(f"Process plan provider {key} differs from Project Lock.")
    expected_harnesses = process_lock.get("target_harnesses", [])
    if list(plan.get("target_harnesses", [])) != list(expected_harnesses):
        failures.append("Process plan harness list differs from Project Lock.")

    locked_status = str(process_lock.get("status", ""))
    evidence_status = str(evidence.get("status", ""))
    if locked_status and evidence_status and locked_status != evidence_status:
        failures.append("Process evidence status differs from Project Lock.")
    runtime_verified = bool(evidence.get("runtime_verified", False))
    if locked_status == "PLANNED_NOT_INSTALLED" and runtime_verified:
        failures.append("Plan-only process integration cannot claim runtime_verified=true.")
    if locked_status == "INSTALLED_CONTRACT_VERIFIED":
        integration_json = project_root / ".specify" / "integration.json"
        if not integration_json.is_file():
            failures.append("Installed Spec Kit process is missing .specify/integration.json.")

    return {
        "status": "FAILED" if failures else (locked_status or "UNKNOWN"),
        "failures": failures,
        "runtime_verified": runtime_verified,
        "provider": locked_provider,
    }
