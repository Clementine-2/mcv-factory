from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml


class HarnessError(RuntimeError):
    """Raised when harness context materialization or verification fails."""


@dataclass(frozen=True)
class HarnessSpec:
    id: str
    adapter_version: str
    context_file: str
    executable: str
    default: bool
    upstream_contract: dict[str, Any]
    notes: str


@dataclass(frozen=True)
class HarnessMaterialization:
    id: str
    adapter_version: str
    context_file: str
    contract_sha256: str
    context_sha256: str
    runtime_status: str
    upstream_contract: dict[str, Any]
    upstream_source_modified: bool = False


DEFAULT_HARNESS_REGISTRY = Path(__file__).resolve().parent / "registry_data" / "harnesses.yaml"
CANONICAL_CONTRACT_PATH = Path(".project/contract/agent-contract.md")
HARNESS_EVIDENCE_PATH = Path(".project/evidence/harness-compatibility.json")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_harness_registry(path: Path | None = None) -> dict[str, HarnessSpec]:
    registry_path = Path(path) if path is not None else DEFAULT_HARNESS_REGISTRY
    data = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise HarnessError("Harness registry must be a mapping.")
    items = data.get("harnesses", [])
    if not isinstance(items, list) or not items:
        raise HarnessError("Harness registry must declare at least one harness adapter.")
    result: dict[str, HarnessSpec] = {}
    for item in items:
        if not isinstance(item, dict):
            raise HarnessError("Harness entries must be mappings.")
        spec = HarnessSpec(
            id=str(item["id"]),
            adapter_version=str(item["adapter_version"]),
            context_file=str(item["context_file"]),
            executable=str(item.get("executable", "")),
            default=bool(item.get("default", False)),
            upstream_contract=dict(item.get("upstream_contract", {})),
            notes=str(item.get("notes", "")),
        )
        if spec.id in result:
            raise HarnessError(f"Duplicate harness adapter id: {spec.id}")
        if not spec.context_file or Path(spec.context_file).is_absolute() or ".." in Path(spec.context_file).parts:
            raise HarnessError(f"Harness {spec.id!r} has an unsafe context_file.")
        result[spec.id] = spec
    return result


def default_harness_ids(registry: dict[str, HarnessSpec] | None = None) -> tuple[str, ...]:
    registry = registry or load_harness_registry()
    selected = tuple(spec.id for spec in registry.values() if spec.default)
    if not selected:
        raise HarnessError("Harness registry has no default adapters.")
    return selected


def resolve_harnesses(
    harness_ids: Iterable[str] | None,
    registry: dict[str, HarnessSpec] | None = None,
) -> tuple[HarnessSpec, ...]:
    registry = registry or load_harness_registry()
    ids = tuple(harness_ids) if harness_ids is not None else default_harness_ids(registry)
    if harness_ids is not None and not ids:
        return ()
    seen: set[str] = set()
    resolved: list[HarnessSpec] = []
    for harness_id in ids:
        if harness_id in seen:
            continue
        seen.add(harness_id)
        spec = registry.get(harness_id)
        if spec is None:
            raise HarnessError(f"Unknown harness adapter {harness_id!r}.")
        resolved.append(spec)
    return tuple(resolved)


def render_agent_contract(
    project_name: str,
    blueprint: dict[str, Any],
    *,
    profile_id: str,
    layout: dict[str, str],
    verification_commands: list[list[str]],
    extension_artifacts: list[dict[str, Any]] | None = None,
) -> str:
    hard = blueprint.get("constraints", {}).get("hard", [])
    hard_lines = "\n".join(f"- {item}" for item in hard) or "- No additional project-specific hard constraint was explicit in the Blueprint."
    layout_lines = "\n".join(f"- {key}: `{value}`" for key, value in layout.items())
    command_lines = "\n".join("- `" + " ".join(command) + "`" for command in verification_commands)
    extension_artifacts = extension_artifacts or []
    extension_lines = "\n".join(
        f"- {item.get('kind', 'artifact')}: `{item.get('path', '')}`" for item in extension_artifacts
    ) or "- No Factory extensions are enabled for this project."
    from .assembly import profile_next_steps

    next_steps = profile_next_steps(profile_id)
    # B04: MCP tool/resource/prompt manifest is part of the contract, not a Host runtime.
    mcp_section = ""
    if profile_id in {"python-mcp-server", "typescript-mcp-server"}:
        mcp_section = (
            "\n\n## MCP tools (not a Host)\n\n"
            "- tool `echo_purpose` — returns project purpose for host sanity-check; tested via in-memory Client\n"
            "- resource `scaffold://status` — static `mcp server scaffold ready`\n"
            "- prompt `introduce` — user-invoked description; `Purpose: <project purpose>`\n"
            "- Host `Inspector` / live STDIO: run `python scripts/verify_real_host.py` (developer-executed; Factory is not an MCP Host).\n"
            "- TypeScript SDK `1.12.1` with `InMemoryTransport`, Python SDK v2 with `mcp.Client`"
        )
    return f'''# Agent Contract — {project_name}\n\n## Project purpose\n\n{blueprint["project"]["purpose"]}\n\n## Bootstrap state\n\nThis repository is a Factory-generated `{profile_id}` scaffold. Verification is claim-scoped; inspect `.project/evidence/generation-verification.json` before treating any behavior as verified. The Factory has **not** implemented domain-specific behavior.\n\n## Next\n\n{next_steps}{mcp_section}\n\n## Native layout\n\n{layout_lines}\n- project metadata: `.project/`\n\n## Verification commands\n\n{command_lines}\n\n## Extension resources\n\n{extension_lines}\n\nExtension resources are additive. They do not override this canonical contract or the Verification Spine.\n\n## Coding workflow\n\nSee `WORKFLOW.md` (top-level) for the step-by-step runbook a coding agent should follow. Harness context files are byte-identical copies of this canonical contract.\n\n## Hard project constraints\n\n{hard_lines}\n\n## Engineering discipline\n\n- Do not claim completion from an Agent statement alone; attach execution evidence.\n- Prefer native ecosystem tooling and existing dependencies over inventing infrastructure.\n- Do not introduce a Runner, multi-Agent team, or new framework unless the task demonstrates a need.\n- Preserve the original Blueprint and Project Lock as provenance.\n- Destructive or irreversible operations require an explicit recovery plan.\n- Harness-specific files are adapters over this same contract; do not create conflicting per-harness rules.\n\n## Factory upgrade discipline\n\n- Treat Factory upgrades as explicit migrations, never as automatic dependency refreshes.\n- Inspect the DryRun plan and rollback scope before applying Factory-owned overlay changes.\n- A Factory-owned file that diverged from its recorded preimage is a conflict; do not overwrite it silently.\n- Business/source files are outside the Factory overlay unless a future migration explicitly declares otherwise.\n'''


def materialize_harness_contracts(
    project_root: Path,
    contract_text: str,
    harness_specs: Iterable[HarnessSpec],
) -> dict[str, Any]:
    project_root = Path(project_root)
    specs = tuple(harness_specs)
    if not specs:
        return {"status": "SKIPPED", "adapters": {}, "canonical_contract": None, "claims": []}
    canonical = project_root / CANONICAL_CONTRACT_PATH
    canonical.parent.mkdir(parents=True, exist_ok=True)
    canonical.write_text(contract_text, encoding="utf-8")
    canonical_sha = _sha256_file(canonical)

    adapters: dict[str, dict[str, Any]] = {}
    claims: list[dict[str, Any]] = []
    for spec in specs:
        context = project_root / spec.context_file
        context.parent.mkdir(parents=True, exist_ok=True)
        context.write_text(contract_text, encoding="utf-8")
        context_sha = _sha256_file(context)
        runtime_status = "AVAILABLE_UNEXECUTED" if spec.executable and shutil.which(spec.executable) else "UNAVAILABLE"
        materialized = HarnessMaterialization(
            id=spec.id,
            adapter_version=spec.adapter_version,
            context_file=spec.context_file,
            contract_sha256=canonical_sha,
            context_sha256=context_sha,
            runtime_status=runtime_status,
            upstream_contract=spec.upstream_contract,
        )
        adapters[spec.id] = asdict(materialized)
        claims.append(
            {
                "id": f"{spec.id}-context-contract",
                "scope": spec.context_file,
                "status": "VERIFIED" if context_sha == canonical_sha else "FAILED",
                "evidence": {
                    "canonical_path": CANONICAL_CONTRACT_PATH.as_posix(),
                    "canonical_sha256": canonical_sha,
                    "context_sha256": context_sha,
                },
                "limitation": "Harness runtime execution was not performed by Project Factory in this environment.",
            }
        )
        claims.append(
            {
                "id": f"{spec.id}-runtime",
                "scope": spec.executable or spec.id,
                "status": "UNVERIFIED",
                "evidence": {"runtime_probe": runtime_status},
                "limitation": "Executable presence is not equivalent to an end-to-end coding-session test.",
            }
        )

    failed = [claim for claim in claims if claim["status"] == "FAILED"]
    overall = "FAILED" if failed else "PARTIALLY_VERIFIED"
    report = {
        "schema_version": "0.1",
        "status": overall,
        "canonical_contract": {
            "path": CANONICAL_CONTRACT_PATH.as_posix(),
            "sha256": canonical_sha,
        },
        "adapters": adapters,
        "claims": claims,
        "limitations": [
            "Context-file parity is verified; live Codex/Claude Code task execution is outside the current verification evidence.",
            "The same canonical contract is copied byte-for-byte to each harness context file to prevent semantic drift at generation time.",
        ],
    }
    evidence_path = project_root / HARNESS_EVIDENCE_PATH
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def verify_harness_contracts(project_root: Path, harness_lock: dict[str, Any]) -> dict[str, Any]:
    project_root = Path(project_root)
    harness_lock = harness_lock or {}
    if harness_lock.get("status") in {"SKIPPED", "ABSENT"} or (
        not harness_lock.get("adapters") and not harness_lock.get("canonical_contract")
    ):
        return {"status": "SKIPPED", "failures": [], "adapters": {}, "claims": []}
    canonical_rel = harness_lock.get("canonical_contract", {}).get("path", CANONICAL_CONTRACT_PATH.as_posix())
    failures: list[str] = []
    canonical_path = Path(str(canonical_rel))
    if not canonical_rel or "\\" in str(canonical_rel) or canonical_path.is_absolute() or ".." in canonical_path.parts:
        failures.append(f"Unsafe canonical contract path: {canonical_rel}")
        canonical = project_root / CANONICAL_CONTRACT_PATH
        canonical_sha = ""
    else:
        canonical = project_root / canonical_path
        canonical_sha = ""
    if failures or not canonical.is_file():
        failures.append(f"Missing canonical contract: {canonical_rel}")
        canonical_sha = ""
    else:
        canonical_sha = _sha256_file(canonical)
        expected = str(harness_lock.get("canonical_contract", {}).get("sha256", ""))
        if expected and canonical_sha != expected:
            failures.append("Canonical contract hash differs from Project Lock.")

    adapters = harness_lock.get("adapters", {})
    verified: dict[str, Any] = {}
    for harness_id, locked in adapters.items():
        context_file = str(locked.get("context_file", ""))
        context_path = Path(context_file)
        if not context_file or "\\" in context_file or context_path.is_absolute() or ".." in context_path.parts:
            failures.append(f"Unsafe {harness_id} context file: {context_file}")
            continue
        context = project_root / context_path
        if not context.is_file():
            failures.append(f"Missing {harness_id} context file: {context_file}")
            continue
        context_sha = _sha256_file(context)
        expected_context = str(locked.get("context_sha256", ""))
        if expected_context and context_sha != expected_context:
            failures.append(f"{harness_id} context hash differs from Project Lock.")
        if canonical_sha and context_sha != canonical_sha:
            failures.append(f"{harness_id} context diverges from canonical contract.")
        verified[harness_id] = {
            "context_file": context_file,
            "context_sha256": context_sha,
            "matches_canonical": bool(canonical_sha and context_sha == canonical_sha),
            "runtime_status": "UNVERIFIED",
        }

    return {
        "status": "FAILED" if failures else "PARTIALLY_VERIFIED",
        "failures": failures,
        "canonical_sha256": canonical_sha,
        "adapters": verified,
        "runtime_verified": False,
    }
