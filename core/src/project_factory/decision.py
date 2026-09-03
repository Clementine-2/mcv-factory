from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .formulas import DecisionDraft, FormulaAdapterError, FormulaContext, apply_formula_adapter
from .policies import PolicyError, apply_policy_rules
from .registry import FormulaSpec, PolicySpec, Registry, RegistryError, load_registry
from .validator import validate_blueprint


class DecisionError(RuntimeError):
    """Raised when a Formula or Policy cannot produce a safe decision."""


_ALLOWED_INTENT_KINDS = {
    "bootstrap",
    "feature",
    "bugfix",
    "refactor",
    "dependency-upgrade",
    "investigation",
    "documentation",
    "release",
}
_ALLOWED_RISK = {"low", "normal", "high", "critical"}
_ALLOWED_SCOPE = {"tiny", "local", "cross-module", "system", "project"}
_ALLOWED_AUTONOMY = {"interactive", "batch", "long-running"}


@dataclass(frozen=True)
class IntentSnapshot:
    kind: str = "bootstrap"
    change_scope: str = "project"
    risk: str = "normal"
    autonomy: str = "interactive"

    def validate(self) -> None:
        if self.kind not in _ALLOWED_INTENT_KINDS:
            raise DecisionError(f"Unsupported intent kind: {self.kind!r}.")
        if self.change_scope not in _ALLOWED_SCOPE:
            raise DecisionError(f"Unsupported intent change_scope: {self.change_scope!r}.")
        if self.risk not in _ALLOWED_RISK:
            raise DecisionError(f"Unsupported intent risk: {self.risk!r}.")
        if self.autonomy not in _ALLOWED_AUTONOMY:
            raise DecisionError(f"Unsupported intent autonomy: {self.autonomy!r}.")


@dataclass(frozen=True)
class RepositoryState:
    existing_project: bool = False
    clean_worktree: bool | None = None
    test_state: str = "unknown"


@dataclass(frozen=True)
class ExecutionDecision:
    formula_id: str
    formula_version: str
    materialization: str
    verification_depth: str
    agent_topology: str
    parallelism: int
    reviewer_required: bool
    runner_required: bool
    checkpoint_policy: str
    isolation: str
    evidence_required: bool


@dataclass(frozen=True)
class DecisionResult:
    decision: ExecutionDecision
    intent: IntentSnapshot
    repository: RepositoryState
    formulas: tuple[dict[str, str], ...]
    policies: tuple[dict[str, Any], ...]
    trace: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": asdict(self.decision),
            "context": {
                "intent": asdict(self.intent),
                "repository": asdict(self.repository),
            },
            "formulas": list(self.formulas),
            "policies": list(self.policies),
            "trace": list(self.trace),
        }


def _matching_formulas(registry: Registry, intent: IntentSnapshot) -> list[FormulaSpec]:
    matched = [
        item
        for item in registry.formulas.values()
        if "*" in item.applies_to or intent.kind in item.applies_to
    ]
    if not matched:
        raise DecisionError(f"No registered Formula applies to intent {intent.kind!r}.")
    return sorted(matched, key=lambda item: item.priority, reverse=True)


def _matching_policies(registry: Registry, intent: IntentSnapshot) -> list[PolicySpec]:
    matched = [
        item
        for item in registry.policies.values()
        if "*" in item.applies_to or intent.kind in item.applies_to
    ]
    return sorted(matched, key=lambda item: item.priority, reverse=True)


def evaluate_decision(
    blueprint: dict[str, Any],
    *,
    intent: IntentSnapshot | None = None,
    repository: RepositoryState | None = None,
    registry: Registry | None = None,
    extension_runtime: Any | None = None,
) -> DecisionResult:
    intent = intent or IntentSnapshot()
    repository = repository or RepositoryState()
    intent.validate()

    validation = validate_blueprint(blueprint)
    if not validation.is_structurally_valid:
        issue = validation.issues[0] if validation.issues else None
        detail = f" {issue.path}: {issue.message}" if issue else ""
        raise DecisionError("Decision input Blueprint is structurally invalid." + detail)

    registry = registry or load_registry(extension_runtime=extension_runtime)
    formulas = _matching_formulas(registry, intent)
    policies = _matching_policies(registry, intent)
    draft = DecisionDraft()
    trace: list[str] = []
    context = FormulaContext(
        intent_kind=intent.kind,
        intent_risk=intent.risk,
        intent_autonomy=intent.autonomy,
        repository_existing=repository.existing_project,
    )

    try:
        for formula in formulas:
            apply_formula_adapter(formula.adapter, blueprint, context, draft, trace, extension_runtime=extension_runtime)
        for policy in policies:
            apply_policy_rules(policy.id, policy.rules, draft, trace)
    except (FormulaAdapterError, PolicyError) as exc:
        raise DecisionError(str(exc)) from exc

    primary = formulas[0]
    decision = ExecutionDecision(
        formula_id=primary.id,
        formula_version=primary.version,
        materialization=draft.materialization,
        verification_depth=draft.verification_depth,
        agent_topology=draft.agent_topology,
        parallelism=draft.parallelism,
        reviewer_required=draft.reviewer_required,
        runner_required=draft.runner_required,
        checkpoint_policy=draft.checkpoint_policy,
        isolation=draft.isolation,
        evidence_required=draft.evidence_required,
    )
    return DecisionResult(
        decision=decision,
        intent=intent,
        repository=repository,
        formulas=tuple({"id": item.id, "version": item.version, "adapter": item.adapter} for item in formulas),
        policies=tuple({"id": item.id, "version": item.version, "rules": dict(item.rules)} for item in policies),
        trace=tuple(trace),
    )


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json
    from pathlib import Path

    import yaml

    parser = argparse.ArgumentParser(description="Evaluate the engineering decision kernel without executing project work")
    parser.add_argument("blueprint", type=Path)
    parser.add_argument("--kind", default="bootstrap")
    parser.add_argument("--change-scope", default="project")
    parser.add_argument("--risk", default="normal")
    parser.add_argument("--autonomy", default="interactive")
    parser.add_argument("--existing-project", action="store_true")
    parser.add_argument("--dirty", action="store_true")
    args = parser.parse_args(argv)

    blueprint = yaml.safe_load(args.blueprint.read_text(encoding="utf-8"))
    intent = IntentSnapshot(
        kind=args.kind,
        change_scope=args.change_scope,
        risk=args.risk,
        autonomy=args.autonomy,
    )
    repository = RepositoryState(
        existing_project=args.existing_project,
        clean_worktree=False if args.dirty else (True if args.existing_project else None),
    )
    try:
        result = evaluate_decision(blueprint, intent=intent, repository=repository)
    except (DecisionError, RegistryError) as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 4
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
