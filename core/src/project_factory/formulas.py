from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


class FormulaAdapterError(RuntimeError):
    """Raised when a registered Formula adapter is unavailable or invalid."""


@dataclass(frozen=True)
class FormulaContext:
    intent_kind: str
    intent_risk: str
    intent_autonomy: str
    repository_existing: bool


@dataclass
class DecisionDraft:
    materialization: str = "minimal"
    verification_depth: str = "baseline"
    agent_topology: str = "single-main-agent"
    parallelism: int = 1
    reviewer_required: bool = False
    runner_required: bool = False
    checkpoint_policy: str = "milestone"
    isolation: str = "none"
    evidence_required: bool = True


FormulaAdapter = Callable[[dict[str, Any], FormulaContext, DecisionDraft, list[str]], None]


def _quality_levels(blueprint: dict[str, Any]) -> set[str]:
    return {
        str(item.get("level"))
        for item in blueprint.get("constraints", {}).get("quality", [])
        if isinstance(item, dict) and item.get("level")
    }


def _baseline_engineering_formula(
    blueprint: dict[str, Any],
    context: FormulaContext,
    draft: DecisionDraft,
    trace: list[str],
) -> None:
    scale = str(blueprint.get("scope", {}).get("scale_hint", ""))
    if blueprint.get("components") or scale in {"large", "very-large"}:
        draft.materialization = "standard"
        trace.append("formula: project structure suggests standard materialization")
    else:
        draft.materialization = "minimal"
        trace.append("formula: no large-project structure requires more than minimal materialization")

    quality_levels = _quality_levels(blueprint)
    if context.intent_risk == "critical" or "critical" in quality_levels or context.intent_kind == "release":
        draft.verification_depth = "strict"
        draft.reviewer_required = True
        trace.append("formula: critical/release conditions require strict verification and an independent reviewer")
    elif context.intent_risk == "high" or "high" in quality_levels:
        draft.verification_depth = "elevated"
        draft.reviewer_required = True
        trace.append("formula: high-risk/high-quality conditions require elevated verification and review")
    else:
        draft.verification_depth = "baseline"
        trace.append("formula: current intent does not justify elevated verification")

    if context.intent_risk in {"high", "critical"}:
        draft.checkpoint_policy = "before-and-after-change"
        trace.append("formula: high-risk intent requires before/after checkpoints")
    else:
        draft.checkpoint_policy = "milestone"

    if context.repository_existing and context.intent_risk in {"high", "critical"}:
        draft.isolation = "isolated-worktree"
        trace.append("formula: high-risk change to an existing project requests isolation")

    if context.intent_autonomy == "long-running":
        draft.runner_required = True
        trace.append("formula: long-running autonomy requests a runner capability")


_FORMULA_ADAPTERS: dict[str, FormulaAdapter] = {
    "baseline-engineering-v1": _baseline_engineering_formula,
}


def apply_formula_adapter(
    adapter_id: str,
    blueprint: dict[str, Any],
    context: FormulaContext,
    draft: DecisionDraft,
    trace: list[str],
    *,
    extension_runtime: Any | None = None,
) -> None:
    adapter = _FORMULA_ADAPTERS.get(adapter_id)
    if adapter is None and extension_runtime is not None:
        adapter = getattr(extension_runtime, "formula_adapters", {}).get(adapter_id)
    if adapter is None:
        raise FormulaAdapterError(f"Unknown trusted Formula adapter: {adapter_id!r}.")
    adapter(blueprint, context, draft, trace)
