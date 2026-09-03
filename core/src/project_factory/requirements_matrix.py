from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from .registry import RegistryError, load_registry, select_profile
from .semantic import SemanticAdapter, SemanticIntakeResult, UserConfirmedSemanticAdapter, run_semantic_intake


@dataclass(frozen=True)
class RequirementMatrixResult:
    intake: SemanticIntakeResult
    rows: tuple[dict[str, Any], ...]
    profile: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "0.1",
            "readiness": self.intake.validation.readiness_status,
            "structure": self.intake.validation.structure_status,
            "rows": [copy.deepcopy(item) for item in self.rows],
            "questions": list(self.intake.questions),
            "profile": copy.deepcopy(self.profile),
            "blueprint": copy.deepcopy(self.intake.blueprint),
            "metadata": copy.deepcopy(self.intake.metadata),
            "receipt": copy.deepcopy(self.intake.receipt),
        }


def _source(meta: dict[str, Any], path: str, fallback: str = "DERIVED") -> str:
    record = (meta.get("provenance", {}) or {}).get(path, {})
    return str(record.get("source") or fallback)


def _row(
    row_id: str,
    label: str,
    value: Any,
    *,
    source: str,
    editable: bool = True,
    status: str = "OK",
    hint: str = "",
) -> dict[str, Any]:
    return {
        "id": row_id,
        "label": label,
        "value": copy.deepcopy(value),
        "source": source,
        "editable": editable,
        "status": status,
        **({"hint": hint} if hint else {}),
    }


def build_requirement_matrix(text: str, adapter: SemanticAdapter | None = None) -> RequirementMatrixResult:
    intake = run_semantic_intake(text, adapter)
    bp = intake.blueprint
    meta = intake.metadata
    rows: list[dict[str, Any]] = []

    rows.append(_row("purpose", "项目目的", bp.get("project", {}).get("purpose", ""), source=_source(meta, "/project/purpose")))

    products = [str(item.get("kind", "")) for item in bp.get("work_products", [])]
    product_sources = {_source(meta, f"/work_products/{index}/kind") for index in range(len(products))}
    rows.append(
        _row(
            "work_products",
            "交付物类型",
            products,
            source=next(iter(product_sources)) if len(product_sources) == 1 else "MIXED",
            status="NEEDS_INPUT" if not products or products == ["unspecified"] else "OK",
            hint="例如 cli、library、browser-extension、mcp-server、desktop-app、service。",
        )
    )

    technology = bp.get("technology", {}) or {}
    for key, label in (
        ("required", "必须技术"),
        ("preferred", "偏好技术"),
        ("prohibited", "禁止技术"),
    ):
        values = list(technology.get(key, []) or [])
        sources = {_source(meta, f"/technology/{key}/{index}") for index in range(len(values))}
        rows.append(_row(f"technology_{key}", label, values, source=next(iter(sources)) if len(sources) == 1 else ("MIXED" if sources else "UNSET")))

    targets = list(bp.get("targets", []) or [])
    target_sources = {_source(meta, f"/targets/{index}/value") for index in range(len(targets))}
    rows.append(_row("targets", "目标平台", targets, source=next(iter(target_sources)) if len(target_sources) == 1 else ("MIXED" if target_sources else "UNSET")))

    constraints = bp.get("constraints", {}) or {}
    hard = list(constraints.get("hard", []) or [])
    hard_sources = {_source(meta, f"/constraints/hard/{index}") for index in range(len(hard))}
    rows.append(_row("hard_constraints", "硬约束", hard, source=next(iter(hard_sources)) if len(hard_sources) == 1 else ("MIXED" if hard_sources else "UNSET")))

    quality = list(constraints.get("quality", []) or [])
    quality_sources = {_source(meta, f"/constraints/quality/{index}") for index in range(len(quality))}
    rows.append(_row("quality", "质量属性", quality, source=next(iter(quality_sources)) if len(quality_sources) == 1 else ("MIXED" if quality_sources else "UNSET")))

    lifecycle = bp.get("lifecycle", {}) or {}
    rows.append(_row("lifecycle_stage", "生命周期阶段", lifecycle.get("stage", ""), source=_source(meta, "/lifecycle/stage", "UNSET")))
    rows.append(_row("lifecycle_horizon", "生命周期周期", lifecycle.get("horizon", ""), source=_source(meta, "/lifecycle/horizon", "UNSET")))

    scope = bp.get("scope", {}) or {}
    rows.append(_row("scope_scale_hint", "规模提示", scope.get("scale_hint", ""), source=_source(meta, "/scope/scale_hint", "UNSET")))

    profile: dict[str, Any]
    try:
        spec = select_profile(bp, load_registry())
        profile = {
            "status": "MATCHED",
            "id": spec.id,
            "version": spec.version,
            "scaffold_recipe": spec.scaffold_recipe,
            "verification_recipe": spec.verification_recipe,
            "provider_preferences": {key: list(value) for key, value in spec.provider_preferences.items()},
        }
    except RegistryError as exc:
        profile = {"status": "UNMATCHED", "error": str(exc)}

    rows.append(
        _row(
            "profile",
            "生成 Profile",
            profile.get("id", "未匹配"),
            source="DERIVED",
            editable=False,
            status="OK" if profile["status"] == "MATCHED" else "NEEDS_INPUT",
            hint="由确认后的需求矩阵确定，不由 AI 直接指定。",
        )
    )
    return RequirementMatrixResult(intake=intake, rows=tuple(rows), profile=profile)


def _clean_string_list(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        values = [item.strip() for item in values.replace("，", ",").split(",")]
    if not isinstance(values, (list, tuple)):
        raise ValueError("Expected a list or comma-separated string.")
    out: list[str] = []
    for item in values:
        value = str(item).strip()
        if value and value not in out:
            out.append(value)
    return out


def _write_provenance(metadata: dict[str, Any], path: str) -> None:
    provenance = metadata.setdefault("provenance", {})
    provenance[path] = {"source": "EXPLICIT", "note": "Confirmed in Requirement Studio."}


def apply_matrix_overrides(matrix: RequirementMatrixResult, overrides: dict[str, Any]) -> UserConfirmedSemanticAdapter:
    """Return a local, structured adapter representing values the user confirmed.

    Only the bounded Blueprint fields exposed by Requirement Studio may be changed here.
    Schema/readiness validation is still performed by run_semantic_intake before generation.
    """
    bp = copy.deepcopy(matrix.intake.blueprint)
    meta = copy.deepcopy(matrix.intake.metadata)
    meta.setdefault("schema_version", "0.1")
    meta.pop("unresolved", None)

    if "purpose" in overrides:
        purpose = str(overrides["purpose"]).strip()
        if not purpose:
            raise ValueError("项目目的不能为空。")
        bp.setdefault("project", {})["purpose"] = purpose
        _write_provenance(meta, "/project/purpose")

    if "work_products" in overrides:
        products = _clean_string_list(overrides["work_products"])
        if not products:
            raise ValueError("至少需要一个交付物类型。")
        bp["work_products"] = [{"kind": item} for item in products]
        for index in range(len(products)):
            _write_provenance(meta, f"/work_products/{index}/kind")

    tech_changed = any(key in overrides for key in ("technology_required", "technology_preferred", "technology_prohibited"))
    if tech_changed:
        tech: dict[str, list[str]] = {}
        for key in ("required", "preferred", "prohibited"):
            values = _clean_string_list(overrides.get(f"technology_{key}", []))
            if values:
                tech[key] = values
                for index in range(len(values)):
                    _write_provenance(meta, f"/technology/{key}/{index}")
        if tech:
            bp["technology"] = tech
        else:
            bp.pop("technology", None)

    if "targets" in overrides:
        raw = overrides["targets"] or []
        targets: list[dict[str, str]] = []
        if isinstance(raw, str):
            raw = [item.strip() for item in raw.replace("，", ",").split(",") if item.strip()]
        for item in raw:
            if isinstance(item, dict):
                kind = str(item.get("kind", "platform")).strip() or "platform"
                value = str(item.get("value", "")).strip()
            else:
                kind, value = "platform", str(item).strip()
            if value:
                targets.append({"kind": kind, "value": value})
        if targets:
            bp["targets"] = targets
            for index in range(len(targets)):
                _write_provenance(meta, f"/targets/{index}/kind")
                _write_provenance(meta, f"/targets/{index}/value")
        else:
            bp.pop("targets", None)

    constraints = copy.deepcopy(bp.get("constraints", {}) or {})
    if "hard_constraints" in overrides:
        hard = _clean_string_list(overrides["hard_constraints"])
        if hard:
            constraints["hard"] = hard
            for index in range(len(hard)):
                _write_provenance(meta, f"/constraints/hard/{index}")
        else:
            constraints.pop("hard", None)
    if "quality" in overrides:
        raw_quality = overrides["quality"] or []
        quality: list[dict[str, str]] = []
        for item in raw_quality:
            if not isinstance(item, dict):
                continue
            attribute = str(item.get("attribute", "")).strip()
            level = str(item.get("level", "normal")).strip() or "normal"
            if attribute:
                quality.append({"attribute": attribute, "level": level})
        if quality:
            constraints["quality"] = quality
            for index in range(len(quality)):
                _write_provenance(meta, f"/constraints/quality/{index}")
        else:
            constraints.pop("quality", None)
    if constraints:
        bp["constraints"] = constraints
    else:
        bp.pop("constraints", None)

    for override_key, bp_key in (("lifecycle_stage", "stage"), ("lifecycle_horizon", "horizon")):
        if override_key in overrides:
            value = str(overrides[override_key] or "").strip()
            lifecycle = bp.setdefault("lifecycle", {})
            if value:
                lifecycle[bp_key] = value
                _write_provenance(meta, f"/lifecycle/{bp_key}")
            else:
                lifecycle.pop(bp_key, None)
            if not lifecycle:
                bp.pop("lifecycle", None)

    if "scope_scale_hint" in overrides:
        value = str(overrides["scope_scale_hint"] or "").strip()
        if value:
            bp["scope"] = {"scale_hint": value}
            _write_provenance(meta, "/scope/scale_hint")
        else:
            bp.pop("scope", None)

    return UserConfirmedSemanticAdapter(bp, meta)
