from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml


class RunnerError(RuntimeError):
    """Raised when Runner planning, verification, or explicit execution is unsafe."""


@dataclass(frozen=True)
class RunnerSpec:
    id: str
    adapter_version: str
    capability: str
    executable: str
    version_args: tuple[str, ...]
    version_regex: str
    default: bool
    protocol: str
    allowed_harnesses: tuple[str, ...]
    upstream_contract: dict[str, Any]
    features: dict[str, bool]
    boundaries: dict[str, bool]
    notes: str = ""


@dataclass(frozen=True)
class RunnerConfig:
    wall_clock_timeout_sec: int = 14_400
    batch_timeout_sec: int = 1_800
    max_batches: int = 8
    batch_interval_sec: int = 5
    retry_limit: int = 1
    retry_interval_sec: int = 30
    retry_max_interval_sec: int = 120

    def validate(self) -> None:
        if not 300 <= self.wall_clock_timeout_sec <= 43_200:
            raise RunnerError("wall_clock_timeout_sec must be between 300 and 43200 seconds.")
        if not 60 <= self.batch_timeout_sec <= 7_200:
            raise RunnerError("batch_timeout_sec must be between 60 and 7200 seconds.")
        if self.batch_timeout_sec > self.wall_clock_timeout_sec:
            raise RunnerError("batch_timeout_sec cannot exceed wall_clock_timeout_sec.")
        if not 1 <= self.max_batches <= 32:
            raise RunnerError("max_batches must be between 1 and 32.")
        if not 0 <= self.batch_interval_sec <= 600:
            raise RunnerError("batch_interval_sec must be between 0 and 600 seconds.")
        if not 0 <= self.retry_limit <= 3:
            raise RunnerError("retry_limit must be between 0 and 3.")
        if not 0 <= self.retry_interval_sec <= 600:
            raise RunnerError("retry_interval_sec must be between 0 and 600 seconds.")
        if not 0 <= self.retry_max_interval_sec <= 3_600:
            raise RunnerError("retry_max_interval_sec must be between 0 and 3600 seconds.")
        if self.retry_max_interval_sec and self.retry_max_interval_sec < self.retry_interval_sec:
            raise RunnerError("retry_max_interval_sec cannot be smaller than retry_interval_sec.")


DEFAULT_RUNNER_REGISTRY = Path(__file__).resolve().parent / "registry_data" / "runners.yaml"
RUNNER_PLAN_PATH = Path(".project/runner/dagu.yaml")
RUNNER_CONTRACT_PATH = Path(".project/runner/CONTRACT.md")
RUNNER_README_PATH = Path(".project/runner/README.md")
RUNNER_EVIDENCE_PATH = Path(".project/evidence/runner-compatibility.json")
RUNNER_STATE_DIR = Path(".project/runner/state")
RUNNER_STATE_README_PATH = RUNNER_STATE_DIR / "README.md"
CANDIDATE_DONE_PATH = RUNNER_STATE_DIR / "CANDIDATE_DONE.flag"
LAST_BATCH_PATH = RUNNER_STATE_DIR / "LAST_BATCH.md"
RUNNER_ADMISSION_LOCK_PATH = RUNNER_STATE_DIR / "ACTIVE_RUN.lock"

_REQUIRED_DAGU_FEATURES = {
    "dag_timeout",
    "step_timeout",
    "retry_policy",
    "repeat_policy",
    "max_active_runs",
    "max_active_steps",
    "run_status",
    "run_history",
    "harness_run",
}
_FORBIDDEN_OWNERSHIP = {
    "owns_harness",
    "owns_project_logic",
    "owns_verification_truth",
    "owns_extensions",
    "owns_interactive_host",
    "owns_project_lock",
}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _portable_command(command: list[str], cwd: Path, *, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
            env=dict(env) if env is not None else None,
            timeout=30,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "command": [Path(command[0]).name, *command[1:]],
            "returncode": 124,
            "stdout": exc.stdout or "",
            "stderr": (exc.stderr or "") + "\nRunner probe timed out after 30s.",
            "timed_out": True,
        }
    return {
        "command": [Path(command[0]).name, *command[1:]],
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "timed_out": False,
    }


@contextmanager
def _project_admission_lock(project_root: Path):
    """Hold the same-project local admission lock for a foreground Runner start.

    Dagu v2.11.2 retains ``max_active_runs`` but documents it as ignored for
    local DAG-based queues. The Factory therefore uses an OS advisory lock for
    its explicit local ``runner start`` path instead of treating that YAML
    field as the local concurrency authority. The lock is released by the OS
    if this process exits unexpectedly. Its file is runtime state, not backup.
    """

    root = Path(project_root).resolve()
    lock_path = root / RUNNER_ADMISSION_LOCK_PATH
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+b")
    try:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RunnerError("Another Factory-mediated Runner start is already active for this project.") from exc
        else:
            import fcntl

            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise RunnerError("Another Factory-mediated Runner start is already active for this project.") from exc
        try:
            yield
        finally:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


def load_runner_registry(path: Path | None = None) -> dict[str, RunnerSpec]:
    registry_path = Path(path) if path is not None else DEFAULT_RUNNER_REGISTRY
    data = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RunnerError("Runner registry must be a mapping.")
    items = data.get("runners", [])
    if not isinstance(items, list) or not items:
        raise RunnerError("Runner registry must declare at least one Runner provider.")
    result: dict[str, RunnerSpec] = {}
    for item in items:
        if not isinstance(item, dict):
            raise RunnerError("Runner registry entries must be mappings.")
        spec = RunnerSpec(
            id=str(item["id"]),
            adapter_version=str(item["adapter_version"]),
            capability=str(item["capability"]),
            executable=str(item["executable"]),
            version_args=tuple(str(value) for value in item.get("version_args", [])),
            version_regex=str(item["version_regex"]),
            default=bool(item.get("default", False)),
            protocol=str(item.get("protocol", "")),
            allowed_harnesses=tuple(str(value) for value in item.get("allowed_harnesses", [])),
            upstream_contract=dict(item.get("upstream_contract", {})),
            features={str(key): bool(value) for key, value in dict(item.get("features", {})).items()},
            boundaries={str(key): bool(value) for key, value in dict(item.get("boundaries", {})).items()},
            notes=str(item.get("notes", "")),
        )
        if spec.id in result:
            raise RunnerError(f"Duplicate Runner provider id: {spec.id}")
        if spec.capability != "long_running_execution":
            raise RunnerError(f"Runner {spec.id!r} must implement long_running_execution.")
        if not spec.executable or Path(spec.executable).name != spec.executable:
            raise RunnerError(f"Runner {spec.id!r} executable must be a bare binary name.")
        if not spec.allowed_harnesses:
            raise RunnerError(f"Runner {spec.id!r} must declare allowed_harnesses.")
        missing = sorted(name for name in _REQUIRED_DAGU_FEATURES if not spec.features.get(name, False))
        if missing:
            raise RunnerError(f"Runner {spec.id!r} is missing required capability declarations: {', '.join(missing)}")
        forbidden = sorted(name for name in _FORBIDDEN_OWNERSHIP if spec.boundaries.get(name, False))
        if forbidden:
            raise RunnerError(f"Runner {spec.id!r} crosses Factory ownership boundaries: {', '.join(forbidden)}")
        result[spec.id] = spec
    if sum(1 for item in result.values() if item.default) != 1:
        raise RunnerError("Runner registry must declare exactly one default Runner provider.")
    return result


def resolve_runner(runner_id: str | None, registry: dict[str, RunnerSpec] | None = None) -> RunnerSpec:
    registry = registry or load_runner_registry()
    selected = runner_id
    if selected is None:
        selected = next(item.id for item in registry.values() if item.default)
    spec = registry.get(selected)
    if spec is None:
        raise RunnerError(f"Unknown Runner provider {selected!r}.")
    return spec


def probe_runner_runtime(spec: RunnerSpec, *, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    path_value = None if env is None else env.get("PATH")
    executable = shutil.which(spec.executable, path=path_value)
    if not executable:
        return {
            "status": "UNAVAILABLE",
            "executable": spec.executable,
            "version": None,
            "runtime_verified": False,
        }
    result = _portable_command([executable, *spec.version_args], Path.cwd(), env=env)
    output = ((result.get("stdout") or "") + "\n" + (result.get("stderr") or "")).strip()
    match = re.search(spec.version_regex, output)
    version = match.group(1) if match else None
    return {
        "status": "AVAILABLE_UNVALIDATED" if result["returncode"] == 0 and version else "VERSION_PROBE_FAILED",
        "executable": executable,
        "version": version,
        "version_probe": result,
        "runtime_verified": False,
    }


def _completion_condition(runtime_kind: str, scaffolder_executable: str) -> str:
    relative = CANDIDATE_DONE_PATH.as_posix()
    if runtime_kind == "python":
        exe = Path(scaffolder_executable).name
        return (
            f'{exe} --offline run python -c "from pathlib import Path; '
            f'raise SystemExit(0 if Path(\'{relative}\').is_file() else 1)"'
        )
    if runtime_kind == "node":
        return (
            'node -e "process.exit(require(\'node:fs\').existsSync('
            f"'{relative}'"
            ') ? 0 : 1)"'
        )
    raise RunnerError(f"No portable completion condition is defined for runtime kind {runtime_kind!r}.")


def _batch_prompt(project_name: str) -> str:
    return f"""Execute exactly one bounded engineering batch for {project_name}.

Read `.project/contract/agent-contract.md` and `.project/runner/CONTRACT.md` before changing files.
Work on one highest-priority coherent batch only; do not try to keep the Agent session alive indefinitely.
Use the project's native tools and preserve Factory ownership boundaries.
At the end of the batch, write a concise checkpoint to `{LAST_BATCH_PATH.as_posix()}` containing work performed, evidence actually observed, remaining work, and the next batch suggestion.
Only create `{CANDIDATE_DONE_PATH.as_posix()}` when the requested project work appears complete and the documented verification commands are expected to pass.
`CANDIDATE_DONE.flag` is an Agent claim, not verification truth. Dagu will run downstream command gates, and Project Factory Verification remains authoritative.
Do not delete recovery artifacts or rewrite Factory metadata outside the explicit task scope.
"""


def build_runner_plan(
    spec: RunnerSpec,
    project_name: str,
    *,
    harness_id: str,
    verification_commands: list[list[str]],
    runtime_kind: str,
    scaffolder_executable: str,
    config: RunnerConfig | None = None,
) -> dict[str, Any]:
    config = config or RunnerConfig()
    config.validate()
    if harness_id not in spec.allowed_harnesses:
        raise RunnerError(
            f"Runner {spec.id!r} does not declare harness {harness_id!r} as compatible. "
            f"Allowed: {', '.join(spec.allowed_harnesses)}"
        )
    if not verification_commands:
        raise RunnerError("Runner plan requires at least one command verification gate.")
    plan: dict[str, Any] = {
        "name": f"project-factory-{project_name}-long-run",
        "description": "Bounded long-running engineering batches; Project Factory owns policy/evidence, Dagu owns execution lifecycle.",
        "type": "chain",
        "working_dir": "../..",
        "timeout_sec": config.wall_clock_timeout_sec,
        # v2.11.2 ignores max_active_runs for local DAG-based queues. Keep
        # the field as an additional non-local compatibility constraint; the
        # Factory explicit start path owns local same-project admission.
        "max_active_runs": 1,
        "max_active_steps": 1,
        "steps": [
            {
                "id": "engineering_batch",
                "action": "harness.run",
                "with": {
                    "provider": harness_id,
                    "prompt": _batch_prompt(project_name),
                },
                "timeout_sec": config.batch_timeout_sec,
                "retry_policy": {
                    "limit": config.retry_limit,
                    "interval_sec": config.retry_interval_sec,
                    "backoff": True,
                    "max_interval_sec": config.retry_max_interval_sec,
                },
                "repeat_policy": {
                    "repeat": "until",
                    "condition": _completion_condition(runtime_kind, scaffolder_executable),
                    "limit": config.max_batches,
                    "interval_sec": config.batch_interval_sec,
                },
            }
        ],
    }
    for index, command in enumerate(verification_commands, start=1):
        if not command:
            continue
        plan["steps"].append(
            {
                "id": f"verification_gate_{index:02d}",
                "action": "exec",
                "with": {
                    "command": Path(command[0]).name,
                    "args": list(command[1:]),
                },
                "timeout_sec": min(config.batch_timeout_sec, 1_800),
            }
        )
    return plan


def render_runner_contract(spec: RunnerSpec, config: RunnerConfig, harness_id: str) -> str:
    return f"""# Runner Contract

## Purpose

Provide bounded unattended execution for one project by repeatedly invoking finite Agent batches. The Runner does not decide architecture, own project correctness, or replace the Harness.

## Provider

- provider: `{spec.id}`
- protocol: `{spec.protocol}`
- harness: `{harness_id}`
- Factory-mediated same-project live starts: `1` (OS admission lock held by `runner start`)
- Dagu max active steps per run: `1`
- Dagu `max_active_runs: 1`: retained as an additional non-local compatibility constraint; Dagu v2.11.2 documents it as ignored for local DAG-based queues
- wall-clock deadline: `{config.wall_clock_timeout_sec}` seconds
- per-batch timeout: `{config.batch_timeout_sec}` seconds
- maximum batches: `{config.max_batches}`
- retry limit per batch execution: `{config.retry_limit}`

## Ownership boundaries

- Dagu owns scheduling/process lifecycle/run history/retry/timeout while it is running.
- Project Factory owns admission for its explicit local `runner start` path so two Factory-mediated starts for the same project cannot overlap.
- The Harness owns model/tool/session behavior.
- Project Factory owns contracts, policy, Verification semantics, Project Lock, and migrations.
- The Agent owns neither completion truth nor Runner lifecycle.
- AionUI or another Interactive Host is a peer entry point and is not in the Runner execution chain.

## Completion semantics

`{CANDIDATE_DONE_PATH.as_posix()}` is only a candidate-completion signal from the Agent. The generated Dagu plan executes downstream command gates after it appears. A successful Dagu run is still not a substitute for Project Factory's claim-scoped Verification Evidence.

## Recovery

Each Agent batch is finite. The batch writes `{LAST_BATCH_PATH.as_posix()}` as an advisory continuation checkpoint. Dagu run history/logs are Provider runtime state. Do not call same-disk Runner state an independent disaster backup.
"""


def _runner_readme(spec: RunnerSpec, plan_sha256: str, runtime: dict[str, Any]) -> str:
    return f"""# Long Runtime Plan

This project contains a **plan-only** `{spec.id}` integration for `long_running_execution`.

- DAG: `{RUNNER_PLAN_PATH.as_posix()}`
- plan SHA-256: `{plan_sha256}`
- runtime probe at generation: `{runtime.get('status', 'UNVERIFIED')}`

Project Factory does not install Dagu, start a long run during generation, or call an Interactive Host. Before any real execution, run the Runner validation command so Dagu itself validates and dry-runs the generated DAG.

A real start is explicit and requires the exact current plan SHA-256. Use a unique run ID so status/stop/retry operations remain auditable.

For local execution, Project Factory also holds an OS-level same-project admission lock for the foreground `dagu start` call. Dagu's v2.11.2 `max_active_runs` field is not treated as the local concurrency authority because upstream marks it ignored for local DAG-based queues.
"""


def materialize_runner_plan(
    project_root: Path,
    spec: RunnerSpec,
    *,
    project_name: str,
    harness_id: str,
    verification_commands: list[list[str]],
    runtime_kind: str,
    scaffolder_executable: str,
    config: RunnerConfig | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    root = Path(project_root)
    config = config or RunnerConfig()
    plan = build_runner_plan(
        spec,
        project_name,
        harness_id=harness_id,
        verification_commands=verification_commands,
        runtime_kind=runtime_kind,
        scaffolder_executable=scaffolder_executable,
        config=config,
    )
    plan_path = root / RUNNER_PLAN_PATH
    contract_path = root / RUNNER_CONTRACT_PATH
    readme_path = root / RUNNER_README_PATH
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    (root / RUNNER_STATE_DIR).mkdir(parents=True, exist_ok=True)
    (root / RUNNER_STATE_README_PATH).write_text(
        "# Runner Runtime State\n\n"
        "This directory is reserved for runtime continuation state. `CANDIDATE_DONE.flag` is only an Agent claim, and `LAST_BATCH.md` is only an advisory batch checkpoint. Neither is an independent backup.\n",
        encoding="utf-8",
    )
    plan_path.write_text(yaml.safe_dump(plan, allow_unicode=True, sort_keys=False), encoding="utf-8")
    contract_path.write_text(render_runner_contract(spec, config, harness_id), encoding="utf-8")
    plan_sha = _sha256_file(plan_path)
    runtime = probe_runner_runtime(spec, env=env)
    readme_path.write_text(_runner_readme(spec, plan_sha, runtime), encoding="utf-8")
    report = {
        "schema_version": "0.1",
        "status": "PARTIALLY_VERIFIED",
        "provider": {
            "id": spec.id,
            "adapter_version": spec.adapter_version,
            "capability": spec.capability,
            "protocol": spec.protocol,
            "upstream_contract": spec.upstream_contract,
            "upstream_source_modified": False,
        },
        "plan": {
            "path": RUNNER_PLAN_PATH.as_posix(),
            "sha256": plan_sha,
            "harness": harness_id,
            "config": asdict(config),
        },
        "runtime": runtime,
        "claims": [
            {
                "id": "runner-plan-materialized",
                "status": "VERIFIED",
                "scope": RUNNER_PLAN_PATH.as_posix(),
                "evidence": {"sha256": plan_sha},
            },
            {
                "id": "runner-runtime",
                "status": "UNVERIFIED",
                "scope": spec.executable,
                "evidence": {"probe": runtime.get("status")},
                "limitation": "Executable presence or a static Dagu contract is not a live long-run test.",
            },
        ],
        "boundaries": spec.boundaries,
        "limitations": [
            "Project Factory did not install or start Dagu during project generation.",
            "CANDIDATE_DONE.flag is an Agent claim; downstream gates and Factory Verification remain authoritative.",
            "Dagu logs/history are operational state, not an independent disaster backup.",
        ],
    }
    evidence_path = root / RUNNER_EVIDENCE_PATH
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def verify_runner_materialization(project_root: Path, runner_lock: dict[str, Any] | None) -> dict[str, Any]:
    if not runner_lock:
        return {"status": "NOT_CONFIGURED", "failures": [], "runtime_verified": False}
    root = Path(project_root)
    failures: list[str] = []
    plan = runner_lock.get("plan", {})
    relative = str(plan.get("path", RUNNER_PLAN_PATH.as_posix()))
    rel_path = Path(relative)
    if not relative or "\\" in relative or rel_path.is_absolute() or ".." in rel_path.parts:
        failures.append(f"Unsafe Runner plan path: {relative}")
        plan_path = root / RUNNER_PLAN_PATH
        actual_sha = ""
    else:
        plan_path = root / rel_path
        actual_sha = ""
    if failures or not plan_path.is_file():
        failures.append(f"Missing Runner plan: {relative}")
    else:
        actual_sha = _sha256_file(plan_path)
        expected = str(plan.get("sha256", ""))
        if expected and actual_sha != expected:
            failures.append("Runner plan hash differs from Project Lock.")
        try:
            data = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                failures.append("Runner plan is not a YAML mapping.")
            else:
                if data.get("working_dir") != "../..":
                    failures.append("Runner plan no longer resolves execution to the generated project root.")
                if data.get("max_active_runs") != 1:
                    failures.append("Runner plan no longer preserves the additional Dagu max_active_runs compatibility constraint.")
                if data.get("max_active_steps") != 1:
                    failures.append("Runner plan no longer enforces one active step per Dagu run.")
                steps = data.get("steps", [])
                batch = steps[0] if isinstance(steps, list) and steps else {}
                if not isinstance(batch, dict) or batch.get("action") != "harness.run":
                    failures.append("Runner plan first step is not the bounded harness.run batch.")
                if isinstance(batch, dict) and batch.get("repeat_policy", {}).get("limit", 0) < 1:
                    failures.append("Runner plan repeat limit is missing or invalid.")
                gates = steps[1:] if isinstance(steps, list) else []
                for gate in gates:
                    if not isinstance(gate, dict) or gate.get("action") != "exec" or not isinstance(gate.get("with"), dict):
                        failures.append("Runner verification gates must use the Dagu v2.11.2 canonical action: exec form.")
                        break
        except Exception as exc:  # YAML corruption should be reported as a verification failure.
            failures.append(f"Runner plan YAML could not be parsed: {exc}")
    for relative_required in (RUNNER_CONTRACT_PATH, RUNNER_README_PATH, RUNNER_STATE_README_PATH, RUNNER_EVIDENCE_PATH):
        if not (root / relative_required).is_file():
            failures.append(f"Missing Runner materialization file: {relative_required.as_posix()}")
    return {
        "status": "FAILED" if failures else "PARTIALLY_VERIFIED",
        "failures": failures,
        "plan_sha256": actual_sha,
        "runtime_verified": False,
    }


def _locked_runner(project_root: Path) -> tuple[dict[str, Any], RunnerSpec]:
    root = Path(project_root)
    lock_path = root / "project.lock.json"
    if not lock_path.is_file():
        raise RunnerError("project.lock.json is required.")
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    runner_lock = lock.get("runner_integration")
    if not isinstance(runner_lock, dict):
        raise RunnerError("Project does not have a Runner integration.")
    provider_id = str(runner_lock.get("provider", {}).get("id", ""))
    spec = resolve_runner(provider_id)
    check = verify_runner_materialization(root, runner_lock)
    if check["status"] == "FAILED":
        raise RunnerError("Runner materialization failed verification: " + "; ".join(check["failures"]))
    return runner_lock, spec


def validate_runner_runtime(project_root: Path, *, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    root = Path(project_root).resolve()
    runner_lock, spec = _locked_runner(root)
    runtime = probe_runner_runtime(spec, env=env)
    if runtime["status"] != "AVAILABLE_UNVALIDATED":
        raise RunnerError(f"Runner runtime is not available for validation: {runtime['status']}")
    executable = str(runtime["executable"])
    plan_path = str((root / runner_lock["plan"]["path"]).resolve())
    validate_result = _portable_command([executable, "validate", plan_path], root, env=env)
    if validate_result["returncode"] != 0:
        raise RunnerError("Dagu validate failed; refusing Runner execution.")
    dry_result = _portable_command([executable, "dry", plan_path], root, env=env)
    if dry_result["returncode"] != 0:
        raise RunnerError("Dagu dry-run failed; refusing Runner execution.")
    return {
        "status": "DRY_VERIFIED",
        "runtime_verified": False,
        "provider_version": runtime.get("version"),
        "plan_sha256": _sha256_file(root / runner_lock["plan"]["path"]),
        "validate": validate_result,
        "dry_run": dry_result,
        "limitation": "Dagu validated/dry-ran the DAG, but a live long-running Agent session was not completed by this check.",
    }


def start_runner(
    project_root: Path,
    *,
    confirm_plan_sha256: str,
    run_id: str,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", run_id):
        raise RunnerError("run_id must be 1-128 characters using letters, digits, '.', '_' or '-'.")
    root = Path(project_root).resolve()
    runner_lock, spec = _locked_runner(root)
    plan_path_obj = root / runner_lock["plan"]["path"]
    actual_sha = _sha256_file(plan_path_obj)
    if confirm_plan_sha256 != actual_sha:
        raise RunnerError("Explicit confirmation hash does not match the current Runner plan.")
    with _project_admission_lock(root):
        preflight = validate_runner_runtime(root, env=env)
        runtime = probe_runner_runtime(spec, env=env)
        executable = str(runtime["executable"])
        result = _portable_command(
            [executable, "start", "--run-id", run_id, str(plan_path_obj.resolve())],
            root,
            env=env,
        )
    start_command_succeeded = result["returncode"] == 0
    return {
        "status": "START_COMMAND_COMPLETED" if start_command_succeeded else "START_COMMAND_FAILED",
        "run_id": run_id,
        "plan_sha256": actual_sha,
        "preflight": preflight,
        "execution": result,
        "start_command_succeeded": start_command_succeeded,
        "workflow_completion_verified": False,
        "runtime_verified": False,
        "limitation": (
            "A successful dagu start command is execution evidence only. It does not by itself prove "
            "that the long-running workflow, Agent work, or Project Factory verification completed successfully."
        ),
    }


def runner_status(project_root: Path, *, run_id: str, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    root = Path(project_root).resolve()
    runner_lock, spec = _locked_runner(root)
    runtime = probe_runner_runtime(spec, env=env)
    if runtime["status"] != "AVAILABLE_UNVALIDATED":
        raise RunnerError(f"Runner runtime is unavailable: {runtime['status']}")
    dag_name = yaml.safe_load((root / runner_lock["plan"]["path"]).read_text(encoding="utf-8"))["name"]
    result = _portable_command([str(runtime["executable"]), "status", dag_name, "--run-id", run_id], root, env=env)
    return {"status": "EXECUTED", "run_id": run_id, "command_result": result}


def stop_runner(project_root: Path, *, run_id: str, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    root = Path(project_root).resolve()
    runner_lock, spec = _locked_runner(root)
    runtime = probe_runner_runtime(spec, env=env)
    if runtime["status"] != "AVAILABLE_UNVALIDATED":
        raise RunnerError(f"Runner runtime is unavailable: {runtime['status']}")
    dag_name = yaml.safe_load((root / runner_lock["plan"]["path"]).read_text(encoding="utf-8"))["name"]
    result = _portable_command([str(runtime["executable"]), "stop", dag_name, "--run-id", run_id], root, env=env)
    return {"status": "EXECUTED", "run_id": run_id, "command_result": result}


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Project Factory Runner adapter")
    sub = parser.add_subparsers(dest="command", required=True)
    inspect_p = sub.add_parser("inspect")
    inspect_p.add_argument("project_root", type=Path)
    validate_p = sub.add_parser("validate")
    validate_p.add_argument("project_root", type=Path)
    start_p = sub.add_parser("start")
    start_p.add_argument("project_root", type=Path)
    start_p.add_argument("--confirm-plan-sha256", required=True)
    start_p.add_argument("--run-id", required=True)
    status_p = sub.add_parser("status")
    status_p.add_argument("project_root", type=Path)
    status_p.add_argument("--run-id", required=True)
    stop_p = sub.add_parser("stop")
    stop_p.add_argument("project_root", type=Path)
    stop_p.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            lock, spec = _locked_runner(args.project_root)
            result = {
                "status": verify_runner_materialization(args.project_root, lock)["status"],
                "provider": spec.id,
                "runtime": probe_runner_runtime(spec),
                "plan_sha256": lock["plan"]["sha256"],
            }
        elif args.command == "validate":
            result = validate_runner_runtime(args.project_root)
        elif args.command == "start":
            result = start_runner(
                args.project_root,
                confirm_plan_sha256=args.confirm_plan_sha256,
                run_id=args.run_id,
            )
        elif args.command == "status":
            result = runner_status(args.project_root, run_id=args.run_id)
        elif args.command == "stop":
            result = stop_runner(args.project_root, run_id=args.run_id)
        else:
            return 4
    except (RunnerError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 4
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
