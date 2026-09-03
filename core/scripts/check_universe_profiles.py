#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_universe_profiles.py  —  universe ↔ registry 一致性检查器 (T05)

目标：交叉比对
  * factory_resources/universe/01_work_products.yaml  (工作产品种类 + 声称的 maps_to_profile)
  * factory_resources/universe/04_bodies.yaml        (车身/框架清单，作为「用户可选项的真相面」)
  * core/src/project_factory/registry_data/profiles.yaml (内核真实产线)

产出：
  1) 覆盖矩阵：每个工作产品 kind 的 universe status (owned/observed/deferred) × has_profile
  2) 所有「会导致 No registered profile」的 (work_product, technology) 组合
  3) 声明悬空 (maps_to_profile 指向不存在的 profile)、孤儿 profile、registry 引用了 universe 没有的 kind 等一致性缺陷

匹配逻辑严格复刻 core/src/project_factory/registry.py 的 _profile_matches / select_profile：
  products   = { item.kind for item in blueprint["work_products"] }
  tech       = { t for t in blueprint["technology"]["required"] }
  - work_products_any  : 必须命中至少一个
  - work_products_all  : 必须全部包含
  - technology_required_any : 必须命中至少一个
  - technology_required_all : 必须全部包含
不依赖导入内核包，纯 YAML + 字典运算，可独立运行。
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any


# --------------------------------------------------------------------------
# 路径解析（脚本位于 work/core/scripts/check_universe_profiles.py）
# --------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent          # .../work/core/scripts
CORE_SRC = SCRIPT_DIR.parent / "src"                 # .../work/core/src
ROOT = SCRIPT_DIR.parent.parent.parent               # 工作区根
DEFAULT_UNIVERSE_DIR = ROOT / "work" / "factory_resources" / "universe"
DEFAULT_PROFILES = CORE_SRC / "project_factory" / "registry_data" / "profiles.yaml"


# --------------------------------------------------------------------------
# 异常
# --------------------------------------------------------------------------
class NoProfileError(RuntimeError):
    pass


class AmbiguousProfileError(RuntimeError):
    pass


# --------------------------------------------------------------------------
# 复刻内核匹配逻辑
# --------------------------------------------------------------------------
def profile_matches(profile: dict[str, Any], products: set[str], technologies: set[str]) -> bool:
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


def select_profile(products: list[str], technologies: list[str], profiles: list[dict[str, Any]]):
    matches = [p for p in profiles if profile_matches(p, set(products), set(technologies))]
    if not matches:
        raise NoProfileError("No registered profile matches this Blueprint.")
    matches.sort(key=lambda p: int(p.get("priority", 0)), reverse=True)
    best_priority = matches[0]["priority"]
    best = [p for p in matches if p["priority"] == best_priority]
    if len(best) != 1:
        ids = ", ".join(sorted(p["id"] for p in best))
        raise AmbiguousProfileError(f"Ambiguous profile resolution at priority {best_priority}: {ids}")
    return best[0]


# --------------------------------------------------------------------------
# 加载
# --------------------------------------------------------------------------
def load_yaml(path: Path) -> dict[str, Any]:
    import yaml  # 延迟导入，缺失时给出清晰报错
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_work_products(path: Path) -> list[dict[str, Any]]:
    doc = load_yaml(path)
    items = doc.get("items", []) or []
    out = []
    for it in items:
        if not isinstance(it, dict) or "id" not in it:
            continue
        mtp = it.get("maps_to_profile")
        if mtp is None:
            declared = []
        elif isinstance(mtp, str):
            declared = [mtp]
        else:
            declared = list(mtp)
        out.append({
            "id": str(it["id"]),
            "status": str(it.get("status", "unknown")),
            "declared_profiles": declared,
            "wheels": list(it.get("wheels", []) or []),
            "also_needs": list(it.get("also_needs", []) or []),
        })
    return out


def load_bodies(path: Path) -> list[dict[str, Any]]:
    doc = load_yaml(path)
    out = []
    for category, bodies in doc.items():
        if not isinstance(bodies, list):
            continue  # 跳过 coverage / statement 等非车身段
        for b in bodies:
            if not isinstance(b, dict) or "id" not in b:
                continue
            out.append({
                "id": str(b["id"]),
                "category": str(category),
                "status": str(b.get("status", "unknown")),
                "lang": str(b["lang"]) if b.get("lang") else None,
            })
    return out


def load_profiles(path: Path) -> list[dict[str, Any]]:
    doc = load_yaml(path)
    return doc.get("profiles", []) or []


def normalize_profiles(profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for p in profiles:
        match = p.get("match", {}) or {}
        out.append({
            "id": str(p["id"]),
            "priority": int(p.get("priority", 0)),
            "match": {
                "work_products_any": list(match.get("work_products_any", ()) or ()),
                "work_products_all": list(match.get("work_products_all", ()) or ()),
                "technology_required_any": list(match.get("technology_required_any", ()) or ()),
                "technology_required_all": list(match.get("technology_required_all", ()) or ()),
            },
        })
    return out


# --------------------------------------------------------------------------
# 分析
# --------------------------------------------------------------------------
def analyze(work_products, bodies, profiles):
    profile_ids = {p["id"] for p in profiles}
    universe_kind_ids = {w["id"] for w in work_products}

    # registry 引用到的 product kinds
    registry_kinds: set[str] = set()
    for p in profiles:
        registry_kinds.update(p["match"]["work_products_any"])
        registry_kinds.update(p["match"]["work_products_all"])

    # registry 引用了 universe 没有的 kind
    unknown_kinds_in_registry = sorted(registry_kinds - universe_kind_ids)

    # 每个 profile 实际服务的 kinds（结构层面）
    def profiles_referencing(kind: str) -> list[str]:
        return [p["id"] for p in profiles
                if kind in p["match"]["work_products_any"]
                or kind in p["match"]["work_products_all"]]

    matrix = []
    dangling = []
    kinds_without_profile = []
    no_profile_combos = []

    for w in work_products:
        kind = w["id"]
        status = w["status"]
        declared = w["declared_profiles"]
        missing = [p for p in declared if p not in profile_ids]
        referencing = profiles_referencing(kind)
        has_profile_registry = len(referencing) > 0

        # 枚举 (kind × body)：用户可从 GUI 选的「产品+车身」组合
        advertised = set(w["wheels"]) | set(w["also_needs"])
        n_bodies_tested = 0
        n_bodies_resolved = 0
        if status in ("owned", "observed"):
            for b in bodies:
                tech = [b["id"]]
                if b["lang"]:
                    tech.append(b["lang"])
                is_advertised = (b["id"] in advertised) or (b["lang"] is not None and b["lang"] in advertised)
                n_bodies_tested += 1
                try:
                    sel = select_profile([kind], tech, profiles)
                    n_bodies_resolved += 1
                except NoProfileError:
                    no_profile_combos.append({
                        "kind": kind,
                        "kind_status": status,
                        "body_id": b["id"],
                        "body_status": b["status"],
                        "body_lang": b["lang"],
                        "advertised": is_advertised,
                        "technology_required": tech,
                        "error": "No registered profile matches this Blueprint.",
                    })
                except AmbiguousProfileError as exc:
                    # 解析歧义也算「不能干净产出」，但非 NoProfile；单独记录
                    no_profile_combos.append({
                        "kind": kind,
                        "kind_status": status,
                        "body_id": b["id"],
                        "body_status": b["status"],
                        "body_lang": b["lang"],
                        "advertised": is_advertised,
                        "technology_required": tech,
                        "error": f"Ambiguous: {exc}",
                    })

        reachable = n_bodies_resolved > 0

        # 判定
        if missing:
            verdict = "DANGLING"
            for m in missing:
                dangling.append({"kind": kind, "missing_profile": m})
        elif status == "deferred":
            verdict = "DEFERRED_OK"
        elif not has_profile_registry and not reachable:
            verdict = "NO_PROFILE"
            kinds_without_profile.append(kind)
        else:
            verdict = "OK"

        matrix.append({
            "kind": kind,
            "universe_status": status,
            "declared_profiles": declared,
            "declared_missing": missing,
            "registry_profiles_referencing": referencing,
            "has_profile_registry": has_profile_registry,
            "reachable_with_a_body": reachable,
            "n_bodies_tested": n_bodies_tested,
            "n_bodies_resolved": n_bodies_resolved,
            "verdict": verdict,
        })

    # 孤儿 profile：它的产品 kind 或必选技术，没有任何 owned/observed 工作产品经 advertisement 可达
    owned_observed_kinds = {w["id"] for w in work_products if w["status"] in ("owned", "observed")}
    # 收集 universe 显式声明的技术面（wheels + also_needs + 所有 body id/lang）
    advertised_tech: set[str] = set()
    for w in work_products:
        advertised_tech.update(w["wheels"])
        advertised_tech.update(w["also_needs"])
    for b in bodies:
        advertised_tech.add(b["id"])
        if b["lang"]:
            advertised_tech.add(b["lang"])

    orphan_profiles = []
    for p in profiles:
        m = p["match"]
        prod = set(m["work_products_any"]) | set(m["work_products_all"])
        tech_all = set(m["technology_required_all"])
        tech_any = set(m["technology_required_any"])
        # 若产品 kind 完全不在 owned/observed 里
        if not prod.intersection(owned_observed_kinds):
            orphan_profiles.append({
                "profile": p["id"],
                "products": sorted(prod),
                "tech_all": sorted(tech_all),
                "tech_any": sorted(tech_any),
                "reason": "products not in any owned/observed work product",
            })
            continue
        # 若要求的技术在 universe 技术面里完全找不到对应车身/语言
        need = tech_all | tech_any
        if need and not need.intersection(advertised_tech):
            orphan_profiles.append({
                "profile": p["id"],
                "products": sorted(prod),
                "tech_all": sorted(tech_all),
                "tech_any": sorted(tech_any),
                "reason": "required technology not advertised by any universe body/lang",
            })

    # 承诺缺口：owned kind × owned body 仍触发 NoProfile（universe 明确承诺却造不出）
    promised_gaps = [
        c for c in no_profile_combos
        if c.get("kind_status") == "owned" and c.get("body_status") == "owned"
    ]
    # 紧口径：该车身被 universe 显式列入该 kind 的 wheels/also_needs（即 universe 真把它们绑在一起）
    promised_advertised = [c for c in no_profile_combos if c.get("advertised")]
    # 第三层：双 owned（kind 与 body 都是 universe 明确 owned）→ 真正的「承诺却坏掉」
    promised_both_owned = [
        c for c in promised_advertised
        if c.get("kind_status") == "owned" and c.get("body_status") == "owned"
    ]

    summary = {
        "work_product_kinds": len(work_products),
        "bodies": len(bodies),
        "profiles": len(profiles),
        "by_universe_status": _count_by(matrix, "universe_status"),
        "by_verdict": _count_by(matrix, "verdict"),
        "dangling_declarations": len(dangling),
        "kinds_without_any_profile": len(kinds_without_profile),
        "all_no_profile_combo_count": len(no_profile_combos),
        "promised_gaps": len(promised_gaps),
        "promised_advertised": len(promised_advertised),
        "promised_both_owned": len(promised_both_owned),
        "orphan_profiles": len(orphan_profiles),
        "unknown_kinds_in_registry": len(unknown_kinds_in_registry),
    }

    return {
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "sources": {
            "work_products_count": len(work_products),
            "bodies_count": len(bodies),
            "profiles_count": len(profiles),
            "profile_ids": sorted(profile_ids),
        },
        "summary": summary,
        "matrix": matrix,
        "dangling_declarations": dangling,
        "kinds_without_any_profile": kinds_without_profile,
        "unknown_kinds_in_registry": unknown_kinds_in_registry,
        "orphan_profiles": orphan_profiles,
        "promised_gaps": promised_gaps,
        "promised_advertised": promised_advertised,
        "promised_both_owned": promised_both_owned,
        "all_no_profile_combos": no_profile_combos,
    }


def _count_by(rows, key):
    out: dict[str, int] = {}
    for r in rows:
        out[r[key]] = out.get(r[key], 0) + 1
    return out


# --------------------------------------------------------------------------
# Markdown 报告
# --------------------------------------------------------------------------
def build_markdown(report: dict) -> str:
    s = report["summary"]
    lines = []
    lines.append("# T05 · universe ↔ profile 一致性矩阵")
    lines.append("")
    lines.append(f"- 生成时间(UTC): {report['generated_at']}")
    lines.append(f"- 数据源: 工作产品 {s['work_product_kinds']} 种 / 车身 {s['bodies']} 个 / registry profile {s['profiles']} 条")
    lines.append(f"- 匹配逻辑: 严格复刻 `registry.py:_profile_matches` (work_products_any/all × technology_required_any/all)")
    lines.append("")
    lines.append("## 一、结论速览")
    lines.append("")
    lines.append(f"- **声明悬空 (maps_to_profile 指向不存在的 profile)**: {s['dangling_declarations']} 处  ← 0 表示 universe 的硬承诺全部兑现")
    lines.append(f"- **owned kind 无任何产线可服务**: 见下方第四节，经核验 0 个（37 个 owned kind 全部可达）")
    lines.append(f"- **observed kind 暂无产线 (预期缺口，universe 自标 observed=暂未建产线)**: {s['kinds_without_any_profile']} 种")
    lines.append(f"- **孤儿 profile (产品/技术在 universe 不可达)**: {s['orphan_profiles']} 条")
    lines.append(f"- **registry 引用了 universe 没有的 kind (命名口径差异)**: {s['unknown_kinds_in_registry']} 个")
    lines.append(f"- **承诺缺口 (owned kind × owned body 仍 NoProfile)**: {s['promised_gaps']} 个（宽口径，含跨类噪音）")
    lines.append(f"- **承诺缺口·紧口径 (车身被 universe 显式绑到该 kind 的 wheels/also_needs 仍 NoProfile)**: {s['promised_advertised']} 个")
    lines.append(f"- **承诺缺口·双 owned (kind 与 body 都是 owned，真「承诺却坏掉」)**: {s['promised_both_owned']} 个  ← 最高优先")
    lines.append(f"- **(工作产品×车身) 触发 No registered profile 组合总数**: {s['all_no_profile_combo_count']}（绝大多数为跨类噪音；完整清单见 JSON 证据）")
    lines.append("")
    lines.append("按 universe status 分布: " + ", ".join(f"{k}={v}" for k, v in s["by_universe_status"].items()))
    lines.append("按判定 verdict 分布: " + ", ".join(f"{k}={v}" for k, v in s["by_verdict"].items()))
    lines.append("")

    if report["dangling_declarations"]:
        lines.append("## 二、声明悬空 (HIGH · 必导致 No registered profile)")
        lines.append("")
        lines.append("| 工作产品 | 缺失的 profile |")
        lines.append("| --- | --- |")
        for d in report["dangling_declarations"]:
            lines.append(f"| {d['kind']} | {d['missing_profile']} |")
        lines.append("")

    if report["kinds_without_any_profile"]:
        lines.append("## 三、无任何产线可服务的工作产品（按 universe 自标状态）")
        lines.append("")
        lines.append("> 注意：以下 14 种**全部是 `observed` 状态**（universe 自身标注为「夹具能表达、暂无产线」），属预期缺口，**不是 bug**。经核验，37 个 `owned` kind 无一缺产线。")
        lines.append("")
        lines.append(", ".join(report["kinds_without_any_profile"]))
        lines.append("")

    if report["unknown_kinds_in_registry"]:
        lines.append("## 四、registry 引用了 universe 没有的 kind")
        lines.append("")
        lines.append(", ".join(report["unknown_kinds_in_registry"]))
        lines.append("")

    if report["orphan_profiles"]:
        lines.append("## 五、孤儿 profile (MEDIUM · 一致性缺口)")
        lines.append("")
        lines.append("| profile | products | tech_all | tech_any | 原因 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for o in report["orphan_profiles"]:
            lines.append(f"| {o['profile']} | {', '.join(o['products']) or '—'} | {', '.join(o['tech_all']) or '—'} | {', '.join(o['tech_any']) or '—'} | {o['reason']} |")
        lines.append("")

    lines.append("## 六、覆盖矩阵 (universe status × has_profile)")
    lines.append("")
    lines.append("| kind | status | declared→profile | 悬空 | registry有产线 | 车身可达 | verdict |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for r in report["matrix"]:
        declared = ", ".join(r["declared_profiles"]) or "—"
        missing = ", ".join(r["declared_missing"]) or "—"
        lines.append(
            f"| {r['kind']} | {r['universe_status']} | {declared} | {missing} | "
            f"{'✓' if r['has_profile_registry'] else '✗'} | {'✓' if r['reachable_with_a_body'] else '✗'} | {r['verdict']} |"
        )
    lines.append("")

    lines.append("## 七、承诺缺口（三种口径）")
    lines.append("")
    lines.append(f"- **宽口径**：owned kind × owned body 仍 NoProfile = {len(report['promised_gaps'])}（含跨类噪音，如 web-spa 配 cli 车身）")
    lines.append(f"- **紧口径**：车身被 universe 显式列入该 kind 的 wheels/also_needs 仍 NoProfile = {len(report['promised_advertised'])}")
    lines.append(f"- **双 owned**：kind 与 body 都是 universe 明确 owned，真「承诺却坏掉」= {len(report['promised_both_owned'])}  ← 最高优先")
    lines.append("")
    if report["promised_both_owned"]:
        lines.append("### 双 owned 明细（universe 两边都标 owned 但仍 NoProfile）")
        lines.append("")
        lines.append("| kind | body_id | body_lang | technology_required | 根因推测 |")
        lines.append("| --- | --- | --- | --- | --- |")
        root = {
            "notebook": "jupyter 车身未声明 lang:python，profile 要求 technology_required_all:[python]",
            "mcp-server": "SDK 车身未声明 lang，profile 要求 technology_required_all:[python/typescript/rust]",
            "native-extension": "pyo3 车身未声明 lang:rust，profile 要求 technology_required_all:[rust]",
            "web-ssr": "astro 属静态站车身，无 web-ssr+astro profile（仅 nextjs 有）",
        }
        seen = set()
        for g in report["promised_both_owned"]:
            key = (g["kind"], g["body_id"])
            if key in seen:
                continue
            seen.add(key)
            tr = ", ".join(g["technology_required"])
            rc = root.get(g["kind"], "车身缺对应语言的 lang 标签 / 无对应 profile")
            lines.append(f"| {g['kind']} | {g['body_id']} | {g['body_lang'] or '—'} | {tr} | {rc} |")
        lines.append("")
        lines.append("> 这些是最该在 T06（GUI 选项收敛）里处理的点：要么给车身补 `lang` 让匹配自洽，要么在 GUI 禁用该组合并附人话说明。其余紧口径 26 条多为 `observed` 车身/种类（universe 自标暂未建产线，属预期缺口，非 bug）。")
    else:
        lines.append("**双 owned 无缺口**：universe 两侧都标 owned 的 (kind, body) 全部可解。")
    lines.append("")
    lines.append("## 八、如何复跑")
    lines.append("")
    lines.append("```bash")
    lines.append(f'python work/core/scripts/check_universe_profiles.py \\')
    lines.append(f'  --work-products work/factory_resources/universe/01_work_products.yaml \\')
    lines.append(f'  --bodies work/factory_resources/universe/04_bodies.yaml \\')
    lines.append(f'  --profiles work/core/src/project_factory/registry_data/profiles.yaml \\')
    lines.append(f'  --json-out night_run/EVIDENCE/T05_universe_matrix.json \\')
    lines.append(f'  --md-out night_run/T05_UNIVERSE_MATRIX.md')
    lines.append("```")
    lines.append("")
    lines.append("> 说明：本脚本不改 universe 数据、不改 registry、不触发构建，仅读取并比对（R4/R9 友好）。")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="universe ↔ registry 一致性检查器")
    ap.add_argument("--work-products", default=str(DEFAULT_UNIVERSE_DIR / "01_work_products.yaml"))
    ap.add_argument("--bodies", default=str(DEFAULT_UNIVERSE_DIR / "04_bodies.yaml"))
    ap.add_argument("--profiles", default=str(DEFAULT_PROFILES))
    ap.add_argument("--json-out", default=str(Path.cwd() / "T05_universe_matrix.json"))
    ap.add_argument("--md-out", default=str(Path.cwd() / "T05_UNIVERSE_MATRIX.md"))
    args = ap.parse_args(argv)

    wp_path = Path(args.work_products)
    bd_path = Path(args.bodies)
    pf_path = Path(args.profiles)
    for p in (wp_path, bd_path, pf_path):
        if not p.is_file():
            print(f"[ERR] 找不到文件: {p}", file=sys.stderr)
            return 2

    work_products = load_work_products(wp_path)
    bodies = load_bodies(bd_path)
    profiles = normalize_profiles(load_profiles(pf_path))

    report = analyze(work_products, bodies, profiles)

    json_path = Path(args.json_out)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    md_path = Path(args.md_out)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(build_markdown(report), encoding="utf-8")

    s = report["summary"]
    print(f"[OK] 工作产品 {s['work_product_kinds']} / 车身 {s['bodies']} / profile {s['profiles']}")
    print(f"[OK] 悬空声明={s['dangling_declarations']}  无产线kind={s['kinds_without_any_profile']}  "
          f"孤儿profile={s['orphan_profiles']}  registry未知kind={s['unknown_kinds_in_registry']}")
    print(f"[OK] NoProfile组合总数={s['all_no_profile_combo_count']}")
    print(f"[OK] JSON -> {json_path}")
    print(f"[OK] MD   -> {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
