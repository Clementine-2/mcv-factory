from __future__ import annotations

from typing import Any

from .formulas import DecisionDraft


class PolicyError(RuntimeError):
    """Raised when a Policy rule is invalid."""


_ALLOWED_RULES = {
    "max_parallelism",
    "allow_multi_agent",
    "allow_runner",
    "require_evidence",
}


def validate_policy_rules(rules: dict[str, Any]) -> None:
    unknown = sorted(set(rules) - _ALLOWED_RULES)
    if unknown:
        raise PolicyError("Unknown Policy rule(s): " + ", ".join(unknown))
    if "max_parallelism" in rules:
        value = rules["max_parallelism"]
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise PolicyError("max_parallelism must be an integer >= 1.")
    for name in ("allow_multi_agent", "allow_runner", "require_evidence"):
        if name in rules and not isinstance(rules[name], bool):
            raise PolicyError(f"{name} must be boolean.")


def apply_policy_rules(policy_id: str, rules: dict[str, Any], draft: DecisionDraft, trace: list[str]) -> None:
    validate_policy_rules(rules)
    max_parallelism = int(rules.get("max_parallelism", draft.parallelism))
    if draft.parallelism > max_parallelism:
        draft.parallelism = max_parallelism
        trace.append(f"policy:{policy_id}: parallelism clamped to {max_parallelism}")

    if rules.get("allow_multi_agent") is False and draft.agent_topology != "single-main-agent":
        draft.agent_topology = "single-main-agent"
        trace.append(f"policy:{policy_id}: multi-Agent topology suppressed")

    if rules.get("allow_runner") is False and draft.runner_required:
        draft.runner_required = False
        trace.append(f"policy:{policy_id}: runner request suppressed")

    if rules.get("require_evidence") is True:
        draft.evidence_required = True
