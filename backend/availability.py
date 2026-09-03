"""availability.py — 数据驱动的 GUI 选项门禁 (T06)

依据内核 registry 的真实产线 (profiles.yaml) 为 GUI 的「工作产品」与「车身」选项计算可用性，
避免用户选到内核根本产不出的组合（即 T05 锤实的 No registered profile 死路）。

匹配逻辑严格复刻 core/src/project_factory/registry.py:_profile_matches / select_profile，
与 T05 的 check_universe_profiles.py 完全一致。任何业务清单都不硬编码——白名单来自 registry 本身。

Fail-safe：找不到 profiles.yaml 或 yaml 缺失时，全部标记为 available=True，
保持 GUI 现有行为，不引入回归。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import yaml
except Exception:  # pragma: no cover - 缺失时 fail-safe
    yaml = None


# --------------------------------------------------------------------------
# 路径发现：从 backend 向上找 core/src/project_factory/registry_data/profiles.yaml
# --------------------------------------------------------------------------
def _find_profiles() -> Path | None:
    here = Path(__file__).resolve().parent
    candidate = here
    for _ in range(7):
        direct = candidate / "core" / "src" / "project_factory" / "registry_data" / "profiles.yaml"
        if direct.is_file():
            return direct
        nested = candidate / "work" / "core" / "src" / "project_factory" / "registry_data" / "profiles.yaml"
        if nested.is_file():
            return nested
        parent = candidate.parent
        if parent == candidate:
            break
        candidate = parent
    return None


# --------------------------------------------------------------------------
# 复刻内核匹配逻辑（与 T05 check_universe_profiles.py 同义）
# --------------------------------------------------------------------------
def _profile_matches(profile: dict[str, Any], products: set[str], technologies: set[str]) -> bool:
    rules = profile.get("match", {}) or {}
    any_products = set(rules.get("work_products_any", ()) or ())
    if any_products and products.isdisjoint(any_products):
        return False
    all_products = set(rules.get("work_products_all", ()) or ())
    if all_products and not all_products.issubset(products):
        return False
    any_tech = set(rules.get("technology_required_any", ()) or ())
    if any_tech and technologies.isdisjoint(any_tech):
        return False
    all_tech = set(rules.get("technology_required_all", ()) or ())
    if all_tech and not all_tech.issubset(technologies):
        return False
    return True


def _select(profiles: list[dict[str, Any]], products: list[str], technologies: list[str]) -> dict[str, Any] | None:
    matches = [p for p in profiles if _profile_matches(p, set(products), set(technologies))]
    if not matches:
        return None
    matches.sort(key=lambda p: int(p.get("priority", 0)), reverse=True)
    return matches[0]


def load_profiles() -> list[dict[str, Any]]:
    if yaml is None:
        return []
    path = _find_profiles()
    if path is None:
        return []
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return []
    return doc.get("profiles", []) or []


# --------------------------------------------------------------------------
# 对外接口
# --------------------------------------------------------------------------
def annotate_catalog(field_options: dict[str, Any], profiles: list[dict[str, Any]] | None = None) -> tuple[dict[str, Any], dict[str, list[str]]]:
    """返回 (带 available/reason 的 field_options 副本, 车身兼容性表)。

    - 工作产品级：被任一 profile 的 work_products_any/all 命中即 available=True。
    - 车身兼容性：对每个 available 的工作产品，列出「车身 id」中能被 select_profile 解析的子集
      （复刻 generate 路径：车身作为 technology_required 传入）。
    """
    if profiles is None:
        profiles = load_profiles()

    # 深拷贝，避免改动调用方传入的 FIELD_OPTIONS
    annotated: dict[str, Any] = {key: [dict(item) for item in value] for key, value in field_options.items()}

    served_kinds: set[str] = set()
    for p in profiles:
        m = p.get("match", {}) or {}
        served_kinds.update(m.get("work_products_any", ()) or ())
        served_kinds.update(m.get("work_products_all", ()) or ())

    for item in annotated.get("work_products", []):
        wp = item.get("id")
        if wp in served_kinds:
            item["available"] = True
        else:
            item["available"] = False
            item["reason"] = "内核暂无对应产线，暂不能生成（universe 标记为暂未建产线 / 规划中）。"

    body_ids = [str(b.get("id", "")) for b in annotated.get("bodies", []) if str(b.get("id", ""))]
    compatibility: dict[str, list[str]] = {}
    for item in annotated.get("work_products", []):
        wp = item.get("id")
        if not item.get("available", True):
            continue
        ok: list[str] = []
        for bid in body_ids:
            if not bid:
                continue
            # 复刻 generate 路径：车身作为单一 technology 传入
            if _select(profiles, [wp], [bid]) is not None:
                ok.append(bid)
        compatibility[wp] = ok

    return annotated, compatibility


def body_reason(work_product_id: str, body_id: str) -> str:
    return (
        f"「{work_product_id}」目前没有「{body_id}」对应的产线"
        f"（内核会报 No registered profile），请换一个车身或先改工作产品。"
    )
