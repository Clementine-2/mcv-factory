from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import stat
import tempfile
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

import yaml

from .extensions import (
    ExtensionError,
    ExtensionRuntime,
    assert_runtime_matches_lock,
    load_extension_runtime,
    materialize_extension_artifacts,
    verify_extension_receipt,
)
from .recipes import (
    RecipeError,
    clean_ephemeral,
    portable_command_result,
    scaffold_project,
)
from .semantic import SemanticAdapter, run_semantic_intake
from .harness import (
    HarnessError,
    materialize_harness_contracts,
    render_agent_contract,
    resolve_harnesses,
    verify_harness_contracts,
)
from .host import HostError, materialize_host_plans, resolve_hosts, verify_host_materialization
from .runner import (
    RunnerConfig,
    RunnerError,
    materialize_runner_plan,
    resolve_runner,
    verify_runner_materialization,
)
from .process import (
    ProcessIntegrationError,
    build_process_plan,
    execute_process_plan,
    materialize_process_plan,
    resolve_process_integration,
    verify_process_materialization,
)
from .decision import DecisionError, DecisionResult, ExecutionDecision, IntentSnapshot, RepositoryState, evaluate_decision
from .verification import (
    VerificationError,
    assert_required_gates,
    build_verification_suite,
    display_verification_commands,
    execute_verification_suite,
)
from .registry import (
    ProviderRuntime,
    ProfileSpec,
    RegistryError,
    load_registry,
    resolve_providers,
    select_profile,
)
from .overlay import OverlayError, apply_factory_overlay
from .assembly import (
    AssemblyOptions,
    AssemblyPlan,
    REAL_HOST_SCRIPT,
    default_options,
    plan_assembly,
    render_coding_workflow,
    render_profile_skill,
)
from .template import blueprint_from_template, options_from_template


FACTORY_VERSION = "0.14.30"
FACTORY_STAGE = "P∞"
PROJECT_ZIP_MAX_FILES = 10_000
PROJECT_ZIP_MAX_MEMBER_BYTES = 512 * 1024 * 1024
PROJECT_ZIP_MAX_TOTAL_BYTES = 2 * 1024 * 1024 * 1024


class FactoryError(RuntimeError):
    """Raised when the Factory cannot safely generate or verify a project."""


@dataclass(frozen=True)
class ProfileSelection:
    profile_id: str
    profile_version: str
    capabilities: tuple[str, ...]
    materialization: str = "minimal"
    scaffold_recipe: str = ""
    verification_recipe: str = ""


@dataclass(frozen=True)
class ProviderSelection:
    capability: str
    provider_id: str
    provider_version: str
    executable: str
    integration: str = "public-cli"
    upstream_source_modified: bool = False


@dataclass(frozen=True)
class GenerationResult:
    project_name: str
    project_zip: Path
    project_root: Path
    blueprint: dict[str, Any]
    metadata: dict[str, Any]
    semantic_receipt: dict[str, Any]
    decision: ExecutionDecision
    decision_record: dict[str, Any]
    profile: ProfileSelection
    providers: dict[str, ProviderSelection]
    verification: dict[str, Any]
    harness_compatibility: dict[str, Any]
    process_integration: dict[str, Any] | None
    host_integration: dict[str, Any] | None
    runner_integration: dict[str, Any] | None

    @property
    def provider(self) -> ProviderSelection:
        """Backward-compatible convenience for the single P3 scaffolding capability."""
        if "project_scaffolding" not in self.providers:
            raise FactoryError("This generation has no scaffolding provider.")
        return self.providers["project_scaffolding"]


_PROJECT_NAME = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$|^[A-Za-z0-9]$")
MAX_PROJECT_NAME_CHARS = 128


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _safe_project_name(name: str) -> str:
    value = name.strip()
    if not value or len(value) > MAX_PROJECT_NAME_CHARS or not _PROJECT_NAME.fullmatch(value):
        raise FactoryError(
            f"Project name must be 1-{MAX_PROJECT_NAME_CHARS} characters, begin and end with a letter or digit, "
            "and use only letters, digits, '.', '_' or '-' in between."
        )
    return value


def _render_compose_http_overlay(project_name: str, profile_id: str) -> str:
    # C04: Postgres drawing for http-service, not a verification gate.
    return f"""# Compose drawing for {profile_id} ({project_name}). Docker daemon is not a verification gate.
# Usage: docker compose up --build  (requires Docker, UNVERIFIED)
# This is a drawing, not a live DB claim. Keep `TestClient` green.
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: app
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]
  api:
    build: .
    ports: ["8000:8000"]
    environment:
      DATABASE_URL: postgres://app:app@db:5432/app
    depends_on: [db]
volumes:
  pgdata:
"""


def _render_compose_split_overlay(project_name: str) -> str:
    return f"""# Compose drawing for frontend-backend-split ({project_name}). Docker daemon is not a verification gate.
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: app
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]
  api:
    build: ./api
    ports: ["8000:8000"]
    environment:
      DATABASE_URL: postgres://app:app@db:5432/app
    depends_on: [db]
  web:
    build: ./web
    ports: ["3000:3000"]
    depends_on: [api]
volumes:
  pgdata:
"""






def _profile_selection(spec: ProfileSpec) -> ProfileSelection:
    return ProfileSelection(
        profile_id=spec.id,
        profile_version=spec.version,
        capabilities=spec.capabilities,
        materialization=spec.materialization,
        scaffold_recipe=spec.scaffold_recipe,
        verification_recipe=spec.verification_recipe,
    )


def _provider_selection(runtime: ProviderRuntime) -> ProviderSelection:
    return ProviderSelection(
        capability=runtime.spec.capability,
        provider_id=runtime.spec.id,
        provider_version=runtime.version,
        executable=runtime.executable_path,
        integration=runtime.spec.integration,
        upstream_source_modified=runtime.spec.upstream_source_modified,
    )


def derive_execution_decision(
    blueprint: dict[str, Any],
    profile_spec: ProfileSpec | None = None,
    *,
    intent: IntentSnapshot | None = None,
    repository: RepositoryState | None = None,
) -> ExecutionDecision:
    """Backward-compatible public wrapper over the P5 decision kernel.

    The decision kernel itself is profile-independent, but this legacy Factory helper
    still verifies that the Blueprint maps to a supported materialization profile.
    """
    try:
        if profile_spec is None:
            select_profile(blueprint)
        return evaluate_decision(blueprint, intent=intent, repository=repository).decision
    except (DecisionError, RegistryError) as exc:
        raise FactoryError(str(exc)) from exc


def resolve_profile(blueprint: dict[str, Any]) -> ProfileSelection:
    try:
        return _profile_selection(select_profile(blueprint))
    except RegistryError as exc:
        raise FactoryError(str(exc)) from exc


def resolve_provider(
    capability: str,
    provider_id: str | None = None,
    *,
    registry: Any | None = None,
) -> ProviderSelection:
    registry = registry or load_registry()
    if capability not in registry.capabilities:
        raise FactoryError(f"Unknown capability {capability!r}.")
    if provider_id is None:
        candidates = [profile for profile in registry.profiles.values() if capability in profile.capabilities]
        provider_ids: list[str] = []
        for profile in sorted(candidates, key=lambda item: item.priority, reverse=True):
            for candidate in profile.provider_preferences.get(capability, ()):
                if candidate not in provider_ids:
                    provider_ids.append(candidate)
    else:
        provider_ids = [provider_id]
    failures: list[str] = []
    from .registry import inspect_provider

    for candidate in provider_ids:
        spec = registry.providers.get(candidate)
        if spec is None or spec.capability != capability:
            failures.append(f"provider {candidate!r} does not implement {capability!r}")
            continue
        try:
            return _provider_selection(inspect_provider(spec))
        except RegistryError as exc:
            failures.append(str(exc))
    raise FactoryError(
        f"No usable provider for capability {capability!r}: " + (" | ".join(failures) or "no candidates")
    )








def _assert_generation_decision_supported(
    decision: ExecutionDecision,
    profile: ProfileSelection,
    intent: IntentSnapshot,
    repository: RepositoryState,
) -> None:
    """Fail closed when the current materializer cannot honor a Decision."""
    unsupported: list[str] = []
    if intent.kind != "bootstrap":
        unsupported.append(f"intent kind {intent.kind!r} is not a new-project bootstrap")
    if repository.existing_project:
        unsupported.append("existing-project mutation is outside generate_project()")
    if decision.materialization != profile.materialization:
        unsupported.append(
            f"decision materialization {decision.materialization!r} exceeds profile materialization {profile.materialization!r}"
        )
    if decision.verification_depth != "baseline":
        unsupported.append(f"verification depth {decision.verification_depth!r} has no current generation suite")
    if decision.reviewer_required:
        unsupported.append("independent reviewer is required but no reviewer integration is currently available")
    if decision.agent_topology != "single-main-agent" or decision.parallelism != 1:
        unsupported.append("requested Agent topology is not supported by the current generator")
    if decision.isolation != "none":
        unsupported.append(f"isolation mode {decision.isolation!r} is not implemented by generate_project()")
    if unsupported:
        raise FactoryError("Execution Decision cannot be honestly materialized: " + "; ".join(unsupported))


def _write_yaml(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")






























def _render_readme(
    project_name: str,
    blueprint: dict[str, Any],
    profile: ProfileSelection,
    commands: list[list[str]],
    verification: dict[str, Any] | None = None,
) -> str:
    command_blocks = "\n".join(f"```bash\n{' '.join(command)}\n```" for command in commands)
    # E01: evidence summary table
    verification = verification or {}
    status = verification.get("status", "UNKNOWN")
    claims = verification.get("claims", []) or []
    # Build markdown table for claims
    if claims:
        header = "| Claim | Status | Evidence |\n|---|---|---|"
        rows = []
        for claim in claims:
            cid = claim.get("id", "unknown")
            cstatus = claim.get("status", "UNKNOWN")
            ev = claim.get("evidence", {})
            # Summarize evidence: prefer command or path
            if isinstance(ev, dict):
                if "command" in ev:
                    ev_str = "`" + " ".join(ev["command"]) + "`" if isinstance(ev["command"], list) else str(ev["command"])
                elif "path" in ev:
                    ev_str = f"`{ev['path']}`"
                else:
                    ev_str = ", ".join(f"{k}={v}" for k, v in list(ev.items())[:2])
            else:
                ev_str = str(ev)
            rows.append(f"| {cid} | {cstatus} | {ev_str} |")
        evidence_table = header + "\n" + "\n".join(rows)
    else:
        evidence_table = "| Claim | Status | Evidence |\n|---|---|---|\n| (no claims) | " + status + " | see `.project/evidence/generation-verification.json` |"
    return f'''# {project_name}\n\n{blueprint["project"]["purpose"]}\n\n## Status\n\nFactory-generated `{profile.profile_id}` project scaffold. Verification is evidence-scoped; see `.project/evidence/generation-verification.json`. Domain-specific functionality is intentionally not implemented by the Factory.\n\n## Verification\n\n{command_blocks}\n\n## Evidence Summary\n\nOverall: **{status}**\n\n{evidence_table}\n\n> `VERIFIED` = evidence supports claim, `UNVERIFIED` = not yet run or requires external runtime, `FAILED` = gate failed, `BLANK` = empty project.\n\n## Agent development\n\nRead `WORKFLOW.md` for the step-by-step coding runbook, and the generated native harness context file(s). Every harness context is generated from `.project/contract/agent-contract.md`. Provenance is stored in `project.lock.json` and `.project/`.\n'''




def _manifest_entries(project_root: Path) -> list[tuple[str, str]]:
    ignored_roots = {".venv", "dist", "__pycache__", ".git", "node_modules", "coverage"}
    entries: list[tuple[str, str]] = []
    for path in sorted(project_root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(project_root)
        if relative.as_posix() == "PROJECT_MANIFEST.sha256":
            continue
        if any(part in ignored_roots for part in relative.parts):
            continue
        if path.suffix in {".pyc", ".tgz"}:
            continue
        entries.append((_sha256_file(path), relative.as_posix()))
    return entries


def write_project_manifest(project_root: Path) -> Path:
    manifest = project_root / "PROJECT_MANIFEST.sha256"
    lines = [f"{digest}  {relative}" for digest, relative in _manifest_entries(project_root)]
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest


def verify_project_manifest(project_root: Path) -> tuple[bool, list[str]]:
    manifest = project_root / "PROJECT_MANIFEST.sha256"
    if not manifest.exists():
        return False, ["PROJECT_MANIFEST.sha256 is missing"]
    failures: list[str] = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            expected, relative = line.split("  ", 1)
        except ValueError:
            failures.append(f"Malformed manifest line: {line}")
            continue
        rel = Path(relative)
        if not relative or "\\" in relative or rel.is_absolute() or ".." in rel.parts:
            failures.append(f"Unsafe manifest path: {relative}")
            continue
        path = project_root / rel
        if not path.is_file():
            failures.append(f"Missing file: {relative}")
            continue
        if _sha256_file(path) != expected:
            failures.append(f"Hash mismatch: {relative}")
    return not failures, failures


def _zip_directory(project_root: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zip_path.open("xb") as handle:
        with zipfile.ZipFile(handle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(project_root.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(project_root.parent).as_posix())


def _safe_project_zip_member(info: zipfile.ZipInfo) -> PurePosixPath:
    name = info.filename
    path = PurePosixPath(name)
    if not name or "\\" in name or path.is_absolute() or ".." in path.parts or "" in path.parts:
        raise FactoryError(f"Unsafe project ZIP member: {name!r}")
    mode = info.external_attr >> 16
    if mode and stat.S_ISLNK(mode):
        raise FactoryError(f"Project ZIP symbolic-link member is not allowed: {name!r}")
    return path


def _validate_project_zip_inventory(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    files: list[zipfile.ZipInfo] = []
    seen: set[str] = set()
    total = 0
    for info in archive.infolist():
        safe = _safe_project_zip_member(info)
        name = safe.as_posix()
        if name in seen:
            raise FactoryError(f"Duplicate project ZIP member: {name}")
        seen.add(name)
        if info.is_dir():
            continue
        if info.file_size > PROJECT_ZIP_MAX_MEMBER_BYTES:
            raise FactoryError(f"Project ZIP member exceeds safe size limit: {name}")
        total += info.file_size
        if total > PROJECT_ZIP_MAX_TOTAL_BYTES:
            raise FactoryError("Project ZIP exceeds safe total uncompressed size limit.")
        files.append(info)
        if len(files) > PROJECT_ZIP_MAX_FILES:
            raise FactoryError("Project ZIP contains too many files.")
    return files


def _extract_project_zip_safely(archive: zipfile.ZipFile, destination: Path) -> None:
    infos = _validate_project_zip_inventory(archive)
    root = destination.resolve()
    for info in infos:
        safe = _safe_project_zip_member(info)
        target = destination.joinpath(*safe.parts)
        resolved = target.resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise FactoryError(f"Project ZIP member escapes restore root: {info.filename!r}") from exc
        resolved.parent.mkdir(parents=True, exist_ok=True)
        if resolved.exists():
            raise FactoryError(f"Refusing to overwrite restored project member: {info.filename!r}")
        with archive.open(info, "r") as source, resolved.open("xb") as target_handle:
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                target_handle.write(chunk)


def _blank_decision() -> ExecutionDecision:
    return ExecutionDecision(
        formula_id="baseline-engineering",
        formula_version="0.1",
        materialization="minimal",
        verification_depth="baseline",
        agent_topology="single-main-agent",
        parallelism=1,
        reviewer_required=False,
        runner_required=False,
        checkpoint_policy="none",
        isolation="none",
        evidence_required=False,
    )


def _generate_blank(project_name: str, output_dir: Path) -> GenerationResult:
    final_project_root = output_dir / project_name
    final_zip = output_dir / f"{project_name}.zip"
    final_project_root.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(final_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(project_name + "/", "")
    decision = _blank_decision()
    blueprint = {"schema_version": "0.1", "project": {"purpose": "blank"}, "work_products": [{"kind": "unspecified"}]}
    return GenerationResult(
        project_name=project_name,
        project_zip=final_zip,
        project_root=final_project_root,
        blueprint=blueprint,
        metadata={"schema_version": "0.1"},
        semantic_receipt={"adapter": {"id": "blank", "version": "0.1"}},
        decision=decision,
        decision_record={"decision": asdict(decision), "context": {}, "trace": ["blank-assembly"]},
        profile=ProfileSelection("blank", "0.1", (), "empty"),
        providers={},
        verification={"status": "BLANK", "claims": [], "gates": [], "required_gates_passed": True},
        harness_compatibility={"status": "SKIPPED", "adapters": {}},
        process_integration=None,
        host_integration=None,
        runner_integration=None,
    )


def generate_project(
    requirement: str,
    project_name: str,
    output_dir: Path,
    *,
    semantic_adapter: SemanticAdapter | None = None,
    intent: IntentSnapshot | None = None,
    repository: RepositoryState | None = None,
    harnesses: tuple[str, ...] | list[str] | None = None,
    process_integration: str | None = None,
    process_mode: str = "plan",
    process_env: Mapping[str, str] | None = None,
    hosts: tuple[str, ...] | list[str] | None = None,
    runner: str | None = None,
    runner_harness: str | None = None,
    runner_config: RunnerConfig | None = None,
    extension_set: Path | None = None,
    options: AssemblyOptions | None = None,
    spec: dict[str, Any] | None = None,
) -> GenerationResult:
    from .tools import apply_owned_tools_path

    apply_owned_tools_path()
    project_name = _safe_project_name(project_name)
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    final_project_root = output_dir / project_name
    final_zip = output_dir / f"{project_name}.zip"
    if final_project_root.exists() or final_zip.exists():
        raise FactoryError(f"Refusing to overwrite existing output for project {project_name!r}.")

    if options is None:
        options = options_from_template(spec) if spec is not None else default_options()
    if options.nothing_selected():
        return _generate_blank(project_name, output_dir)

    try:
        extension_runtime = load_extension_runtime(extension_set)
    except ExtensionError as exc:
        raise FactoryError(str(exc)) from exc

    if spec is not None:
        from .semantic import SemanticIntakeResult
        from .validator import validate_blueprint

        blueprint = blueprint_from_template(spec)
        metadata = {"schema_version": "0.1", "provenance": {"/project/purpose": {"source": "EXPLICIT"}}}
        validation = validate_blueprint(blueprint, metadata)
        semantic = SemanticIntakeResult(
            blueprint,
            metadata,
            validation,
            (),
            {"adapter": {"id": "structured-spec", "version": "0.1"}},
        )
    else:
        if not str(requirement or "").strip():
            raise FactoryError("Requirement text is empty. Use a template, click-spec, or --blank.")
        semantic = run_semantic_intake(requirement, semantic_adapter)
    if semantic.validation.readiness_status != "USABLE" and not (
        spec is not None and options.scaffold is False
    ):
        questions = "; ".join(semantic.questions) or "Requirement requires resolution."
        raise FactoryError(f"Blueprint is not usable: {semantic.validation.readiness_status}. {questions}")

    registry = load_registry(extension_runtime=extension_runtime)
    plan = plan_assembly(semantic.blueprint, project_name, registry)
    if plan.mode == "reject":
        raise FactoryError(plan.reason)
    if plan.mode == "split" and options.scaffold:
        return _generate_split(
            semantic,
            plan,
            project_name,
            output_dir,
            options=options,
            intent=intent,
            repository=repository,
            harnesses=harnesses,
            process_integration=process_integration,
            process_mode=process_mode,
            process_env=process_env,
            hosts=hosts,
            runner=runner,
            runner_harness=runner_harness,
            runner_config=runner_config,
            extension_runtime=extension_runtime,
            registry=registry,
        )
    try:
        profile_spec = select_profile(semantic.blueprint, registry)
        provider_runtimes = resolve_providers(profile_spec, registry)
    except RegistryError as exc:
        products = [str(item.get("kind") or "") for item in semantic.blueprint.get("work_products", []) if isinstance(item, dict)]
        techs = [str(item) for item in (semantic.blueprint.get("technology") or {}).get("required", [])]
        hint = (
            f"当前组合对不上产线：交付物={products or '空'}，技术={techs or '空'}。"
            " 请只保留互相匹配的一组，例如 React 网页 = web-spa + react；WPF = desktop-app + csharp。"
        )
        raise FactoryError(f"{exc} {hint}" if "No registered profile" in str(exc) else str(exc)) from exc

    profile = _profile_selection(profile_spec)
    providers = {capability: _provider_selection(runtime) for capability, runtime in provider_runtimes.items()}
    intent = intent or IntentSnapshot()
    repository = repository or RepositoryState()
    decision_result: DecisionResult = evaluate_decision(semantic.blueprint, intent=intent, repository=repository, registry=registry, extension_runtime=extension_runtime)
    decision = decision_result.decision
    _assert_generation_decision_supported(decision, profile, intent, repository)
    if not options.harness:
        harnesses = ()
    elif options.harness_ids is not None:
        harnesses = options.harness_ids
    try:
        harness_specs = resolve_harnesses(harnesses)
        process_spec = resolve_process_integration(process_integration)
        process_plan = build_process_plan(process_spec, [item.id for item in harness_specs]) if process_spec else None
        host_specs = resolve_hosts(hosts)
        if runner is not None and intent.autonomy != "long-running":
            raise RunnerError("Explicit Runner materialization requires Intent autonomy='long-running'.")
        runner_spec = resolve_runner(runner) if decision.runner_required else None
        if runner is not None and runner_spec is None:
            raise RunnerError("Runner was requested but the Execution Decision does not require long-running execution.")
    except (HarnessError, ProcessIntegrationError, HostError, RunnerError) as exc:
        raise FactoryError(str(exc)) from exc
    if process_mode not in {"plan", "execute"}:
        raise FactoryError("process_mode must be 'plan' or 'execute'.")
    if process_mode == "execute" and process_spec is None:
        raise FactoryError("process_mode='execute' requires a process_integration.")

    with tempfile.TemporaryDirectory(prefix="project-factory-", ignore_cleanup_errors=True) as temp_dir:
        staging_root = Path(temp_dir)
        project_root = staging_root / project_name
        try:
            if options.scaffold:
                scaffold_result = scaffold_project(
                    profile.scaffold_recipe,
                    providers["project_scaffolding"],
                    project_name,
                    project_root,
                    staging_root,
                    semantic.blueprint["project"]["purpose"],
                    extension_runtime=extension_runtime,
                )
                # C04: optional Postgres compose drawing for http-service (docker up UNVERIFIED)
                if options.with_compose and profile.profile_id in {
                    "python-http-service",
                    "csharp-http-service",
                    "typescript-http-nest",
                    "typescript-http-hono",
                    "rust-http-service",
                }:
                    compose_path = project_root / "compose.yaml"
                    compose_path.write_text(
                        _render_compose_http_overlay(project_name, profile.profile_id), encoding="utf-8"
                    )
                    # expose in layout for contract
                    try:
                        scaffold_result.layout["compose"] = "compose.yaml"
                    except Exception:
                        pass
            else:
                project_root.mkdir(parents=True, exist_ok=False)
                from .recipes import ScaffoldResult

                scaffold_result = ScaffoldResult(command_result={}, layout={})
            if options.verification and options.scaffold:
                verification_suite = build_verification_suite(
                    profile.verification_recipe, project_name, providers["project_scaffolding"], extension_runtime=extension_runtime
                )
                display_commands = display_verification_commands(verification_suite)
            else:
                verification_suite = None
                display_commands = []
        except (RecipeError, VerificationError) as exc:
            raise FactoryError(str(exc)) from exc

        try:
            extension_receipt = materialize_extension_artifacts(project_root, extension_runtime)
        except ExtensionError as exc:
            raise FactoryError(str(exc)) from exc

        layout = scaffold_result.layout if options.scaffold else {}
        contract_text = render_agent_contract(
            project_name,
            semantic.blueprint,
            profile_id=profile.profile_id,
            layout=layout,
            verification_commands=display_commands,
            extension_artifacts=list(extension_receipt["artifacts"]),
        )
        try:
            harness_compatibility = materialize_harness_contracts(project_root, contract_text, harness_specs)
            if harness_compatibility["status"] == "FAILED":
                raise FactoryError("Harness contract materialization failed.")
            host_evidence = materialize_host_plans(project_root, host_specs, harness_compatibility["adapters"])
            runner_evidence = None
            if runner_spec is not None:
                selected_runner_harness = runner_harness or harness_specs[0].id
                if selected_runner_harness not in {item.id for item in harness_specs}:
                    raise RunnerError(
                        f"Runner harness {selected_runner_harness!r} is not among the materialized harnesses: "
                        + ", ".join(item.id for item in harness_specs)
                    )
                runner_evidence = materialize_runner_plan(
                    project_root,
                    runner_spec,
                    project_name=project_name,
                    harness_id=selected_runner_harness,
                    verification_commands=display_commands,
                    runtime_kind=verification_suite.runtime_kind,
                    scaffolder_executable=providers["project_scaffolding"].executable,
                    config=runner_config,
                )
            process_evidence = None
            if process_spec and process_plan:
                process_evidence = materialize_process_plan(project_root, process_plan)
                if process_mode == "execute":
                    process_evidence = execute_process_plan(
                        project_root, process_spec, process_plan, env=process_env
                    )
        except (HarnessError, ProcessIntegrationError, HostError, RunnerError) as exc:
            raise FactoryError(str(exc)) from exc
        # README is written after verification so it can include evidence summary (E01)
        try:
            if options.overlay:
                apply_factory_overlay(
                    project_root,
                    project_name=project_name,
                    profile_id=profile.profile_id,
                    factory_version=FACTORY_VERSION,
                )
        except OverlayError as exc:
            raise FactoryError(str(exc)) from exc

        project_meta = project_root / ".project"
        _write_yaml(project_meta / "blueprint.yaml", semantic.blueprint)
        _write_yaml(project_meta / "blueprint.meta.yaml", semantic.metadata)

        generated_at = datetime.now(timezone.utc).isoformat()
        blueprint_hash = _sha256_bytes(_json_bytes(semantic.blueprint))
        lock_providers = {
            capability: {
                "id": provider.provider_id,
                "version": provider.provider_version,
                "integration": provider.integration,
                "upstream_source_modified": provider.upstream_source_modified,
                "compatibility_state": "SUPPORTED",
            }
            for capability, provider in providers.items()
        }
        lock = {
            "lock_schema_version": "0.9",
            "factory": {"version": FACTORY_VERSION, "stage": FACTORY_STAGE},
            "project_name": project_name,
            "generated_at_utc": generated_at,
            "blueprint_schema_version": semantic.blueprint["schema_version"],
            "blueprint_sha256": blueprint_hash,
            "semantic_intake": semantic.receipt,
            "formula": {"id": decision.formula_id, "version": decision.formula_version},
            "formulas": list(decision_result.formulas),
            "policies": list(decision_result.policies),
            "profile": {
                "id": profile.profile_id,
                "version": profile.profile_version,
                "scaffold_recipe": profile.scaffold_recipe,
                "verification_recipe": profile.verification_recipe,
                "verification_suite": (
                    {"id": verification_suite.id, "version": verification_suite.version}
                    if verification_suite is not None
                    else None
                ),
            },
            "capabilities": list(profile.capabilities) + (["long_running_execution"] if runner_evidence else []),
            "providers": lock_providers,
            "compatibility_policy": {
                "provider_generation_requires": "SUPPORTED",
                "automatic_promotion": False,
            },
            "upgrade_contract": {
                "version": "0.3",
                "dry_run_required": True,
                "automatic_apply": False,
                "rollback_before_apply": True,
                "business_files_outside_overlay": True,
            },
            "harness_contract": {
                "status": harness_compatibility["status"],
                "canonical_contract": harness_compatibility["canonical_contract"],
                "adapters": harness_compatibility["adapters"],
                "runtime_verified": False,
            },
            "host_integration": (
                {
                    "status": host_evidence["status"],
                    "runtime_verified": False,
                    "hosts": host_evidence["hosts"],
                }
                if host_evidence
                else None
            ),
            "runner_integration": (
                {
                    "status": runner_evidence["status"],
                    "runtime_verified": False,
                    "provider": runner_evidence["provider"],
                    "plan": runner_evidence["plan"],
                    "boundaries": runner_evidence["boundaries"],
                }
                if runner_evidence
                else None
            ),
            "extension_contract": {
                "api_version": "1",
                "automatic_code_loading": False,
                "state_required_for_reverification": bool(extension_runtime.extensions),
            },
            "extensions": [item.receipt() for item in extension_runtime.extensions],
            "extension_artifacts": list(extension_receipt["artifacts"]),
            "process_integration": (
                {
                    "provider": process_evidence["provider"],
                    "status": process_evidence["status"],
                    "runtime_verified": bool(process_evidence.get("runtime_verified", False)),
                    "target_harnesses": list(process_plan["target_harnesses"]),
                    "agent_context_extension": bool(process_plan["agent_context_extension"]),
                }
                if process_evidence and process_plan
                else None
            ),
            "execution_decision": asdict(decision),
            "decision_context": decision_result.to_dict()["context"],
            "decision_trace": list(decision_result.trace),
        }
        _write_json(project_root / "project.lock.json", lock)
        _write_json(project_meta / "extensions.lock.json", extension_receipt)
        scaffolder = providers["project_scaffolding"]
        _write_json(
            project_meta / "generation.json",
            {
                "generated_at_utc": generated_at,
                "semantic_intake": semantic.receipt,
                "execution_decision": decision_result.to_dict(),
                "resolution": {
                    "profile": {"id": profile.profile_id, "version": profile.profile_version},
                    "capabilities": list(profile.capabilities) + (["long_running_execution"] if runner_evidence else []),
                    "providers": lock_providers,
                    "harnesses": [item.id for item in harness_specs],
                    "hosts": [item.id for item in host_specs],
                    "process_integration": process_spec.id if process_spec else None,
                    "process_mode": process_mode if process_spec else None,
                    "runner": runner_spec.id if runner_spec else None,
                    "runner_harness": runner_evidence["plan"]["harness"] if runner_evidence else None,
                    "extensions": [item.receipt() for item in extension_runtime.extensions],
                },
                "scaffolder": {
                    "capability": scaffolder.capability,
                    "provider": scaffolder.provider_id,
                    "version": scaffolder.provider_version,
                    "command_result": (
                        portable_command_result(scaffold_result.command_result, project_root=project_root, staging_root=staging_root)
                        if scaffold_result.command_result
                        else {}
                    ),
                },
                "factory_boundary": "bootstrap-only; domain feature intentionally not implemented",
                "factory_upgrade_contract": {
                    "version": "0.3",
                    "dry_run_required": True,
                    "automatic_apply": False,
                    "factory_owned_files_only": True,
                },
            },
        )

        try:
            if verification_suite is not None:
                verification = execute_verification_suite(
                    verification_suite, project_root, providers["project_scaffolding"]
                )
                verification["generated_at_utc"] = generated_at
                assert_required_gates(verification)
            else:
                verification = {
                    "status": "SKIPPED",
                    "claims": [],
                    "gates": [],
                    "required_gates_passed": True,
                    "generated_at_utc": generated_at,
                }
        except VerificationError as exc:
            raise FactoryError(str(exc)) from exc
        lock["verification"] = {
            "status": verification["status"],
            "suite": verification.get("suite"),
            "claim_summary": verification.get("claim_summary"),
        }
        _write_json(project_meta / "evidence" / "generation-verification.json", verification)
        # E01: README with evidence summary (after verification so it can show VERIFIED/UNVERIFIED)
        if options.readme:
            (project_root / "README.md").write_text(
                _render_readme(project_name, semantic.blueprint, profile, display_commands, verification), encoding="utf-8"
            )
        # Q4-①: always-on coding runbook so the project is caught by an agent out of the box.
        if options.scaffold:
            (project_root / "WORKFLOW.md").write_text(
                render_coding_workflow(
                    project_name,
                    profile.profile_id,
                    verification_commands=display_commands,
                    real_host_script=REAL_HOST_SCRIPT.get(profile.profile_id),
                ),
                encoding="utf-8",
            )
        from .ownership import collect_managed_file_hashes, managed_paths_from_lock
        lock["managed_files"] = collect_managed_file_hashes(project_root, managed_paths_from_lock(lock))
        lock["upgrade_history"] = []
        _write_json(project_root / "project.lock.json", lock)

        clean_ephemeral(project_root)
        from .ownership import write_factory_overlay_manifest
        write_factory_overlay_manifest(project_root, list(managed_paths_from_lock(lock)) + ["project.lock.json"])
        write_project_manifest(project_root)
        ok, failures = verify_project_manifest(project_root)
        if not ok:
            raise FactoryError("Generated project manifest failed before packaging: " + "; ".join(failures))
        shutil.copytree(project_root, final_project_root)

    _zip_directory(final_project_root, final_zip)
    return GenerationResult(
        project_name=project_name,
        project_zip=final_zip,
        project_root=final_project_root,
        blueprint=semantic.blueprint,
        metadata=semantic.metadata,
        semantic_receipt=semantic.receipt,
        decision=decision,
        decision_record=decision_result.to_dict(),
        profile=profile,
        providers=providers,
        verification=verification,
        harness_compatibility=harness_compatibility,
        process_integration=process_evidence,
        host_integration=host_evidence,
        runner_integration=runner_evidence,
    )


def _generate_split(
    semantic: Any,
    plan: AssemblyPlan,
    project_name: str,
    output_dir: Path,
    *,
    options: AssemblyOptions,
    intent: IntentSnapshot | None,
    repository: RepositoryState | None,
    harnesses: tuple[str, ...] | list[str] | None,
    process_integration: str | None,
    process_mode: str,
    process_env: Mapping[str, str] | None,
    hosts: tuple[str, ...] | list[str] | None,
    runner: str | None,
    runner_harness: str | None,
    runner_config: RunnerConfig | None,
    extension_runtime: Any,
    registry: Any,
) -> GenerationResult:
    del process_env, runner, runner_harness, runner_config, process_integration, process_mode
    final_project_root = output_dir / project_name
    final_zip = output_dir / f"{project_name}.zip"
    intent = intent or IntentSnapshot()
    repository = repository or RepositoryState()
    if not options.harness:
        harnesses = ()
    elif options.harness_ids is not None:
        harnesses = options.harness_ids
    try:
        harness_specs = resolve_harnesses(harnesses)
        host_specs = resolve_hosts(hosts)
    except (HarnessError, HostError) as exc:
        raise FactoryError(str(exc)) from exc
    profile = ProfileSelection(plan.profile_id, "0.1", ("project_scaffolding",), "minimal")
    decision_result = evaluate_decision(
        semantic.blueprint, intent=intent, repository=repository, registry=registry, extension_runtime=extension_runtime
    )
    _assert_generation_decision_supported(decision_result.decision, profile, intent, repository)
    purpose = semantic.blueprint["project"]["purpose"]
    with tempfile.TemporaryDirectory(prefix="project-factory-", ignore_cleanup_errors=True) as temp_dir:
        staging_root = Path(temp_dir)
        project_root = staging_root / project_name
        project_root.mkdir(parents=True, exist_ok=False)
        package_verifications: list[dict[str, Any]] = []
        layouts: dict[str, Any] = {}
        providers: dict[str, ProviderSelection] = {}
        lock_packages: list[dict[str, Any]] = []
        extra_ids: list[str] = []
        for pkg in plan.packages:
            spec = registry.profiles[pkg.profile_id]
            extra_ids.append(spec.id)
            runtimes = resolve_providers(spec, registry)
            provider = _provider_selection(runtimes["project_scaffolding"])
            providers[pkg.directory] = provider
            if "project_scaffolding" not in providers:
                providers["project_scaffolding"] = provider
            pkg_root = project_root / pkg.directory
            try:
                scaffold_result = scaffold_project(
                    spec.scaffold_recipe, provider, pkg.project_name, pkg_root, staging_root, purpose, extension_runtime=extension_runtime
                )
            except RecipeError as exc:
                raise FactoryError(str(exc)) from exc
            layouts[pkg.directory] = scaffold_result.layout
            lock_packages.append(
                {
                    "dir": pkg.directory,
                    "profile": spec.id,
                    "project_name": pkg.project_name,
                    "scaffold_recipe": spec.scaffold_recipe,
                    "verification_recipe": spec.verification_recipe,
                    "provider": provider.provider_id,
                }
            )
            if options.verification:
                try:
                    suite = build_verification_suite(spec.verification_recipe, pkg.project_name, provider, extension_runtime=extension_runtime)
                    report = execute_verification_suite(suite, pkg_root, provider)
                    assert_required_gates(report)
                except VerificationError as exc:
                    raise FactoryError(str(exc)) from exc
                package_verifications.append(report)
        layout = {f"{pkg.directory}/{key}": f"{pkg.directory}/{value}" for pkg in plan.packages for key, value in layouts.get(pkg.directory, {}).items()}
        layout["api"] = "api/"
        layout["web"] = "web/"
        # C04: optional compose for split when api is http-service
        if options.with_compose and any(
            pid in {"python-http-service", "csharp-http-service", "typescript-http-nest", "typescript-http-hono", "rust-http-service"}
            for pid in extra_ids
        ):
            (project_root / "compose.yaml").write_text(_render_compose_split_overlay(project_name), encoding="utf-8")
            layout["compose"] = "compose.yaml"
        display_commands: list[list[str]] = []
        for report in package_verifications:
            for gate in report.get("gates", []):
                command = (gate.get("observed") or {}).get("command") or (gate.get("expected") or {}).get("command")
                if command:
                    display_commands.append(list(command) if isinstance(command, list) else [str(command)])
        contract_text = render_agent_contract(
            project_name,
            semantic.blueprint,
            profile_id=plan.profile_id,
            layout=layout,
            verification_commands=display_commands or [["(see api/ and web/ packages)"]],
        )
        try:
            harness_compatibility = materialize_harness_contracts(project_root, contract_text, harness_specs)
            host_evidence = materialize_host_plans(project_root, host_specs, harness_compatibility.get("adapters") or {})
        except (HarnessError, HostError) as exc:
            raise FactoryError(str(exc)) from exc
        try:
            if options.overlay:
                apply_factory_overlay(
                    project_root,
                    project_name=project_name,
                    profile_id=plan.profile_id,
                    factory_version=FACTORY_VERSION,
                    extra_profile_ids=tuple(extra_ids),
                )
        except OverlayError as exc:
            raise FactoryError(str(exc)) from exc
        generated_at = datetime.now(timezone.utc).isoformat()
        if package_verifications:
            statuses = {item.get("status") for item in package_verifications}
            if "FAILED" in statuses:
                merged_status = "FAILED"
            elif "VERIFIED" in statuses and len(statuses) == 1:
                merged_status = "VERIFIED"
            else:
                merged_status = "PARTIALLY_VERIFIED"
            verification = {
                "status": merged_status,
                "packages": package_verifications,
                "required_gates_passed": all(item.get("required_gates_passed") for item in package_verifications),
                "claims": [claim for item in package_verifications for claim in item.get("claims", [])],
                "gates": [gate for item in package_verifications for gate in item.get("gates", [])],
                "generated_at_utc": generated_at,
            }
        else:
            verification = {"status": "SKIPPED", "claims": [], "gates": [], "required_gates_passed": True, "generated_at_utc": generated_at}
        project_meta = project_root / ".project"
        _write_yaml(project_meta / "blueprint.yaml", semantic.blueprint)
        _write_yaml(project_meta / "blueprint.meta.yaml", semantic.metadata)
        lock_providers = {
            "project_scaffolding": {
                "id": providers["project_scaffolding"].provider_id,
                "version": providers["project_scaffolding"].provider_version,
                "integration": providers["project_scaffolding"].integration,
                "upstream_source_modified": providers["project_scaffolding"].upstream_source_modified,
                "compatibility_state": "SUPPORTED",
            }
        }
        lock = {
            "lock_schema_version": "0.9",
            "factory": {"version": FACTORY_VERSION, "stage": FACTORY_STAGE},
            "project_name": project_name,
            "generated_at_utc": generated_at,
            "blueprint_schema_version": semantic.blueprint["schema_version"],
            "blueprint_sha256": _sha256_bytes(_json_bytes(semantic.blueprint)),
            "semantic_intake": semantic.receipt,
            "profile": {"id": plan.profile_id, "version": "0.1", "scaffold_recipe": "", "verification_recipe": ""},
            "assembly": {"kind": plan.profile_id, "packages": lock_packages},
            "providers": lock_providers,
            "harness_contract": {
                "status": harness_compatibility["status"],
                "canonical_contract": harness_compatibility.get("canonical_contract"),
                "adapters": harness_compatibility.get("adapters") or {},
                "runtime_verified": False,
            },
            "execution_decision": asdict(decision_result.decision),
            "verification": {"status": verification["status"]},
        }
        _write_json(project_root / "project.lock.json", lock)
        _write_json(project_meta / "evidence" / "generation-verification.json", verification)
        # E01: README with evidence summary for split
        if options.readme:
            (project_root / "README.md").write_text(
                _render_readme(project_name, semantic.blueprint, profile, display_commands, verification), encoding="utf-8"
            )
        # Q4-①: always-on coding runbook (split packages each have their own profile; use the split profile id).
        if options.scaffold:
            (project_root / "WORKFLOW.md").write_text(
                render_coding_workflow(
                    project_name,
                    plan.profile_id,
                    verification_commands=display_commands,
                    real_host_script=REAL_HOST_SCRIPT.get(plan.profile_id),
                ),
                encoding="utf-8",
            )
        from .ownership import collect_managed_file_hashes, managed_paths_from_lock, write_factory_overlay_manifest

        lock["managed_files"] = collect_managed_file_hashes(project_root, managed_paths_from_lock(lock))
        _write_json(project_root / "project.lock.json", lock)
        clean_ephemeral(project_root)
        write_factory_overlay_manifest(project_root, list(managed_paths_from_lock(lock)) + ["project.lock.json"])
        write_project_manifest(project_root)
        ok, failures = verify_project_manifest(project_root)
        if not ok:
            raise FactoryError("Generated project manifest failed before packaging: " + "; ".join(failures))
        shutil.copytree(project_root, final_project_root)
    _zip_directory(final_project_root, final_zip)
    return GenerationResult(
        project_name=project_name,
        project_zip=final_zip,
        project_root=final_project_root,
        blueprint=semantic.blueprint,
        metadata=semantic.metadata,
        semantic_receipt=semantic.receipt,
        decision=decision_result.decision,
        decision_record=decision_result.to_dict(),
        profile=profile,
        providers=providers,
        verification=verification,
        harness_compatibility=harness_compatibility,
        process_integration=None,
        host_integration=host_evidence,
        runner_integration=None,
    )


def restore_verify_project_zip(zip_path: Path, *, extension_set: Path | None = None) -> dict[str, Any]:
    zip_path = Path(zip_path).resolve()
    if not zip_path.exists():
        raise FactoryError(f"Project ZIP does not exist: {zip_path}")
    with tempfile.TemporaryDirectory(prefix="project-factory-p11-restore-", ignore_cleanup_errors=True) as temp_dir:
        temp_root = Path(temp_dir)
        try:
            with zipfile.ZipFile(zip_path, "r") as archive:
                bad = archive.testzip()
                if bad:
                    raise FactoryError(f"ZIP CRC verification failed for {bad}")
                _extract_project_zip_safely(archive, temp_root)
        except zipfile.BadZipFile as exc:
            raise FactoryError("Project ZIP is not a valid ZIP archive.") from exc
        roots = [item for item in temp_root.iterdir() if item.is_dir()]
        if len(roots) != 1:
            raise FactoryError("Project ZIP must contain exactly one top-level project directory.")
        project_root = roots[0]
        if not (project_root / "project.lock.json").is_file():
            return {
                "status": "BLANK",
                "project_name": project_root.name,
                "profile": "blank",
                "manifest_verified": True,
                "verification": {"status": "BLANK", "required_gates_passed": True},
            }
        ok, failures = verify_project_manifest(project_root)
        if not ok:
            raise FactoryError("Restored project manifest failed: " + "; ".join(failures))
        lock = json.loads((project_root / "project.lock.json").read_text(encoding="utf-8"))
        try:
            extension_runtime = load_extension_runtime(extension_set)
            assert_runtime_matches_lock(extension_runtime, lock.get("extensions", []))
            extension_receipt = json.loads((project_root / ".project/extensions.lock.json").read_text(encoding="utf-8"))
            extension_check = verify_extension_receipt(project_root, extension_receipt)
            if extension_check["status"] == "FAILED":
                raise FactoryError("Restored extension artifacts failed: " + "; ".join(extension_check["failures"]))
        except (ExtensionError, FileNotFoundError, json.JSONDecodeError) as exc:
            raise FactoryError(str(exc)) from exc
        harness_check = verify_harness_contracts(project_root, lock.get("harness_contract", {}))
        if harness_check["status"] == "FAILED":
            raise FactoryError("Restored harness contract failed: " + "; ".join(harness_check["failures"]))
        host_check = verify_host_materialization(project_root, lock.get("host_integration"))
        if host_check["status"] == "FAILED":
            raise FactoryError("Restored Host integration failed: " + "; ".join(host_check["failures"]))
        runner_check = verify_runner_materialization(project_root, lock.get("runner_integration"))
        if runner_check["status"] == "FAILED":
            raise FactoryError("Restored Runner integration failed: " + "; ".join(runner_check["failures"]))
        process_check = verify_process_materialization(project_root, lock.get("process_integration"))
        if process_check["status"] == "FAILED":
            raise FactoryError("Restored process integration failed: " + "; ".join(process_check["failures"]))
        profile_id = lock["profile"]["id"]
        registry = load_registry(extension_runtime=extension_runtime)
        assembly = lock.get("assembly") or {}
        packages = list(assembly.get("packages") or [])
        if packages:
            reports = []
            for pkg in packages:
                spec = registry.profiles.get(str(pkg.get("profile")))
                if spec is None:
                    raise FactoryError(f"Locked assembly profile {pkg.get('profile')!r} is not present in the current registry.")
                provider = resolve_provider("project_scaffolding", str(pkg.get("provider") or spec.provider_preferences["project_scaffolding"][0]), registry=registry)
                try:
                    suite = build_verification_suite(spec.verification_recipe, str(pkg.get("project_name") or lock["project_name"]), provider, extension_runtime=extension_runtime)
                    report = execute_verification_suite(suite, project_root / str(pkg["dir"]), provider)
                    assert_required_gates(report)
                except VerificationError as exc:
                    raise FactoryError(str(exc)) from exc
                reports.append(report)
            statuses = {item.get("status") for item in reports}
            verification = {
                "status": "FAILED" if "FAILED" in statuses else ("VERIFIED" if statuses == {"VERIFIED"} else "PARTIALLY_VERIFIED"),
                "packages": reports,
                "required_gates_passed": all(item.get("required_gates_passed") for item in reports),
            }
        else:
            profile_spec = registry.profiles.get(profile_id)
            if profile_spec is None:
                raise FactoryError(f"Locked profile {profile_id!r} is not present in the current registry.")
            providers = {}
            for capability, locked in lock["providers"].items():
                providers[capability] = resolve_provider(capability, locked["id"], registry=registry)
            recipe = lock["profile"].get("verification_recipe")
            if not recipe:
                verification = {"status": lock.get("verification", {}).get("status") or "SKIPPED", "required_gates_passed": True}
            else:
                try:
                    suite = build_verification_suite(
                        recipe,
                        lock["project_name"],
                        providers["project_scaffolding"],
                        extension_runtime=extension_runtime,
                    )
                    verification = execute_verification_suite(
                        suite, project_root, providers["project_scaffolding"]
                    )
                    assert_required_gates(verification)
                except VerificationError as exc:
                    raise FactoryError(str(exc)) from exc
        return {
            "status": verification["status"],
            "zip_sha256": _sha256_file(zip_path),
            "project_name": lock["project_name"],
            "profile": profile_id,
            "manifest_verified": True,
            "verification": verification,
            "harness_compatibility": harness_check,
            "process_integration": process_check,
            "host_integration": host_check,
            "runner_integration": runner_check,
            "extensions": extension_check,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Project Factory generation and restore verification")
    sub = parser.add_subparsers(dest="command", required=True)

    generate = sub.add_parser("generate", help="Generate a project from a supported profile with evidence-first verification")
    generate.add_argument("--name", required=True)
    generate.add_argument("--output-dir", required=True, type=Path)
    generate.add_argument("--harness", action="append", dest="harnesses", help="Harness adapter id; repeat for multiple")
    generate.add_argument("--process-integration", help="Optional process integration id")
    generate.add_argument("--process-mode", choices=("plan", "execute"), default="plan")
    generate.add_argument("--host", action="append", dest="hosts", help="Interactive Host adapter id; repeat for multiple")
    generate.add_argument("--autonomy", choices=("interactive", "batch", "long-running"), default="interactive")
    generate.add_argument("--runner", help="Long-running execution Provider id; requires --autonomy long-running")
    generate.add_argument("--runner-harness", help="Harness id used by the Runner; defaults to the first materialized harness")
    generate.add_argument("--runner-wall-clock-sec", type=int, default=14400)
    generate.add_argument("--runner-batch-sec", type=int, default=1800)
    generate.add_argument("--runner-max-batches", type=int, default=8)
    generate.add_argument("--runner-retry-limit", type=int, default=1)
    generate.add_argument("--extension-set", type=Path, help="Explicit Extension Set state file")
    generate.add_argument("requirement")

    verify = sub.add_parser("restore-verify", help="Extract and re-verify a generated project ZIP")
    verify.add_argument("zip_path", type=Path)
    verify.add_argument("--extension-set", type=Path, help="Extension Set required by the locked project")

    args = parser.parse_args(argv)
    try:
        if args.command == "generate":
            result = generate_project(
                args.requirement,
                args.name,
                args.output_dir,
                harnesses=tuple(args.harnesses) if args.harnesses else None,
                process_integration=args.process_integration,
                process_mode=args.process_mode,
                hosts=tuple(args.hosts) if args.hosts else None,
                intent=IntentSnapshot(autonomy=args.autonomy),
                runner=args.runner,
                runner_harness=args.runner_harness,
                runner_config=RunnerConfig(
                    wall_clock_timeout_sec=args.runner_wall_clock_sec,
                    batch_timeout_sec=args.runner_batch_sec,
                    max_batches=args.runner_max_batches,
                    retry_limit=args.runner_retry_limit,
                ),
                extension_set=args.extension_set,
            )
            print(
                json.dumps(
                    {
                        "status": result.verification["status"],
                        "project": str(result.project_root),
                        "zip": str(result.project_zip),
                        "profile": result.profile.profile_id,
                        "providers": {key: value.provider_id for key, value in result.providers.items()},
                        "harnesses": sorted(result.harness_compatibility["adapters"]),
                        "harness_status": result.harness_compatibility["status"],
                        "process_integration": result.process_integration["status"] if result.process_integration else None,
                        "hosts": sorted(result.host_integration["hosts"]) if result.host_integration else [],
                        "host_status": result.host_integration["status"] if result.host_integration else None,
                        "runner": result.runner_integration["provider"]["id"] if result.runner_integration else None,
                        "runner_status": result.runner_integration["status"] if result.runner_integration else None,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        if args.command == "restore-verify":
            print(json.dumps(restore_verify_project_zip(args.zip_path, extension_set=args.extension_set), ensure_ascii=False, indent=2))
            return 0
    except FactoryError as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 4
    return 4
