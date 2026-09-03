"""Selection advisor — pre-flight warnings for the assembly UI.

Goal: tell the user, *while they are still clicking checkboxes*, whether the current
selection will (a) be rejected by the factory (互斥 / MUTEX) or (b) build but likely
silently prefer one product over another they also picked (功能重叠 / OVERLAP), or
(c) carry a tech/body mismatch the factory would reject.

This is the UX counterpart to ``assembly.plan_assembly``: the planner is the authoritative
"will it build" decision; this module translates that decision (plus family/overlap
heuristics) into human wording so the GUI never has to surface a cryptic
"Refusing to silently drop work products …" after the fact.

Single source of truth: the registry. No hardcoded business lists of kinds. The
car-type *family* of every profile is declared in ``profiles.yaml`` (registry O1), so
adding a new car series requires zero advisor code changes — the grouping below is
fully derived from ``profile.family``.
"""
from __future__ import annotations

from typing import Any

from .assembly import plan_assembly
from .registry import load_registry


# Kind->family grouping is read from the registry, not hardcoded. These codes only
# steer the GUI color: web/service overlaps are the common cases the user hits most.
_OVERLAP_CODE_BY_FAMILY = {
    "web": "OVERLAP_WEB",
    "service": "OVERLAP_SERVICE",
}

# Human-readable family labels for the warning text. Anything not listed falls back
# to the raw family token (still unambiguous in the UI).
_FAMILY_LABEL = {
    "web": "Web 前端",
    "service": "后端服务",
    "cli": "命令行工具",
    "library": "库",
    "desktop": "桌面应用",
    "extension": "扩展",
    "agent": "Agent/SDK",
    "data": "数据/AI",
    "deploy": "部署/基建",
    "comms": "通信/实时",
    "test": "测试",
}


def _kind_family(registry: Any, kind: str) -> str:
    """The car-type family a work-product kind belongs to.

    Derived from the registry: every profile that would build ``kind`` declares a
    ``family``; profiles sharing a kind share a family, so the lookup is stable.
    """
    for profile in registry.profiles.values():
        any_products = set(profile.match.get("work_products_any", ()) or ())
        if kind in any_products:
            return profile.family or kind
    return kind


def _required_tech(registry: Any, kind: str) -> set[str]:
    """Tech a kind's profile(s) demand (technology_required_all ∪ technology_required_any)."""
    needed: set[str] = set()
    for profile in registry.profiles.values():
        any_products = set(profile.match.get("work_products_any", ()) or ())
        if kind not in any_products:
            continue
        needed.update(profile.match.get("technology_required_all", ()) or ())
        needed.update(profile.match.get("technology_required_any", ()) or ())
    return needed


def advise_selection(
    work_products: list[str],
    technology: list[str] | None = None,
) -> dict[str, Any]:
    """Return structured, human-readable warnings for a prospective selection.

    Returns ``{"warnings": [...], "has_error": bool, "has_warn": bool}`` where each warning
    is ``{"level": "error"|"warn", "code": str, "msg": str}``.
    """
    kinds = [str(k) for k in (work_products or [])]
    tech = [str(t) for t in (technology or [])]
    warnings: list[dict[str, str]] = []

    # --- Nothing selected yet ---
    if not kinds:
        warnings.append({
            "level": "error",
            "code": "EMPTY",
            "msg": "请至少选择一项工作产品（车型）。",
        })
        return {"warnings": warnings, "has_error": True, "has_warn": False}

    registry = load_registry()
    families = {k: _kind_family(registry, k) for k in kinds}

    # --- Hard mutex: anything the factory would reject (authoritative planner) ---
    bp: dict[str, Any] = {"work_products": [{"kind": k} for k in kinds]}
    if tech:
        bp["technology"] = {"required": tech, "preferred": [], "prohibited": []}
    plan = plan_assembly(bp, "advisory")
    if plan.mode == "reject":
        selected_families = set(families.values())
        if "web" in selected_families and "service" in selected_families:
            msg = (
                "这些产品不能同时装配：前后端拆分只接受 1 个 Web 前端 + 1 个 http-service，"
                "其余产品会被丢弃。请只保留这两项，或只保留一项单独生成。"
            )
        else:
            msg = (
                "这些产品互斥：工厂一次只装配一个车型（工作产品），"
                "或仅 1 个 Web 前端 + 1 个 http-service 的前后拆分。请只保留一项。"
            )
        warnings.append({"level": "error", "code": "MUTEX", "msg": msg})

    # --- Soft overlap: buildable, but likely a mistake (one product silently preferred) ---
    # Group selected kinds by their declared family. Any family with more than one
    # picked kind means the factory will build one and silently ignore the rest.
    fam_groups: dict[str, list[str]] = {}
    for k in kinds:
        fam_groups.setdefault(families[k], []).append(k)
    for fam, ks in fam_groups.items():
        if len(ks) > 1:
            code = _OVERLAP_CODE_BY_FAMILY.get(fam, "OVERLAP_SAME_TYPE")
            label = _FAMILY_LABEL.get(fam, fam)
            warnings.append({
                "level": "warn",
                "code": code,
                "msg": (
                    f"功能重叠：你勾了多个同属「{label}」家族的产品（{', '.join(sorted(ks))}）。"
                    "一个项目通常只用一个；工厂会用其中一个，其余被忽略。"
                ),
            })

    # --- Tech / body mismatch: a picked product needs a tech you didn't supply ---
    for k in kinds:
        needed = _required_tech(registry, k)
        if needed and tech and not (set(needed) & set(tech)):
            warnings.append({
                "level": "warn",
                "code": "TECH_MISMATCH",
                "msg": (
                    f"技术错配：{k} 的可选车身/技术为 {sorted(needed)}，"
                    f"你选的 {sorted(tech)} 不在其中。"
                ),
            })

    return {
        "warnings": warnings,
        "has_error": any(w["level"] == "error" for w in warnings),
        "has_warn": any(w["level"] == "warn" for w in warnings),
    }
