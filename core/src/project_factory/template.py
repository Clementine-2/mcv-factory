"""Assembly template export/import for click-spec and web AI fill-in."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .assembly import AssemblyOptions
from .validator import validate_blueprint

TEMPLATE_SCHEMA = "project-factory-assembly-template/1"

AI_FILL_INSTRUCTIONS = """你在帮「Project Factory / 基地车工厂」整理需求。

工厂是什么：把想法变成可以继续开发的项目骨架（车架）。它不写业务功能、不编页面文案、不编 API 路径、不编数据库表。

你该做的：把用户的话改写成工厂能吃的信息。能确定的字段写进 YAML；不确定就留空，不要猜。

工厂能吃的字段：
- project_name: 小写字母数字短横线
- purpose: 一句话目的
- work_products: 只能用这些 kind（可多选）：cli, library, http-service, web-spa, web-ui, web-ssr, desktop-app, tui, scraper, mcp-server, browser-extension, notebook, docs-site, static-site, graphql-api, grpc-service, realtime-service, bot, serverless-function, container-stack, vscode-extension, ci-action, rag-application, model-serving
- language: python / typescript / javascript / rust / csharp
- body: typer / react / vue / svelte / nextjs / hono / nestjs / axum / clap / avalonia / commander / astro / textual，或留空
- repo: single-package 或 frontend-backend-split（只有同时要 http-service 和 web-spa 时才用 split）
- options.*: true/false。全 false = 空目录

硬规则：
- 不要发明 fullstack、website、app 这种 kind。FastAPI+React 是 http-service + web-spa。
- 组合是多个 kind，不是新 kind。`frontend-backend-split` 是双目录拓扑，不是新 kind（C01/C03）。
- 工厂生成原生仓结构，不是领域功能。
- Do not invent work_product kinds. Use only the allowed list above.
- 可选：`options.with_compose: true` 仅对 `http-service`（含 split 的 `api`）追加 `compose.yaml`（Postgres 图纸，`docker compose up` 仍 UNVERIFIED，C04）。

输出格式（必须两段）：
1) 给用户看的中文描述：保留原意，用工厂的 kind/语言把类型说清楚。
2) 一个 YAML 代码块，schema 必须是 project-factory-assembly-template/1，按下面模板填，不要删字段。
"""


def empty_template() -> dict[str, Any]:
    return {
        "schema": TEMPLATE_SCHEMA,
        "ai_instructions": AI_FILL_INSTRUCTIONS,
        "project_name": "",
        "purpose": "",
        "work_products": [],
        "language": "",
        "body": "",
        "repo": "single-package",
        "options": {
            "scaffold": True,
            "verification": True,
            "overlay": True,
            "harness": True,
            "readme": True,
            "harnesses": ["codex", "claude"],
            "with_compose": False,  # C04: optional Postgres compose drawing for http-service
        },
    }


def export_template(path: Path | None = None) -> dict[str, Any]:
    payload = empty_template()
    if path is not None:
        Path(path).write_text(
            yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
    return payload


def load_template(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Assembly template must be a mapping.")
    if str(payload.get("schema") or "") != TEMPLATE_SCHEMA:
        raise ValueError(f"Unsupported template schema: {payload.get('schema')!r}")
    return payload


def options_from_template(payload: dict[str, Any]) -> AssemblyOptions:
    raw = payload.get("options") or {}
    harnesses = raw.get("harnesses")
    harness_ids = tuple(str(item) for item in harnesses) if isinstance(harnesses, list) else None
    harness = bool(raw.get("harness", True))
    if harness_ids is not None and len(harness_ids) == 0:
        harness = False
    return AssemblyOptions(
        scaffold=bool(raw.get("scaffold", True)),
        verification=bool(raw.get("verification", True)),
        overlay=bool(raw.get("overlay", True)),
        harness=harness,
        readme=bool(raw.get("readme", True)),
        harness_ids=harness_ids if harness else (),
        with_compose=bool(raw.get("with_compose", False)),
    )


def blueprint_from_template(payload: dict[str, Any]) -> dict[str, Any]:
    purpose = str(payload.get("purpose") or "").strip() or "Structured assembly"
    products_raw = payload.get("work_products") or []
    products = [{"kind": str(item)} for item in products_raw if str(item).strip()]
    blueprint: dict[str, Any] = {
        "schema_version": "0.1",
        "project": {"purpose": purpose},
        "work_products": products or [{"kind": "unspecified"}],
    }
    language = str(payload.get("language") or "").strip()
    body = str(payload.get("body") or "").strip()
    required = [item for item in (language, body) if item]
    if required:
        blueprint["technology"] = {"required": required}
    repo = str(payload.get("repo") or "").strip()
    if repo == "frontend-backend-split" and products:
        kinds = {item["kind"] for item in products}
        if "http-service" not in kinds and "service" not in kinds:
            products.append({"kind": "http-service"})
        if not ({"web-ui", "web-spa", "web-ssr"} & {item["kind"] for item in products}):
            products.append({"kind": "web-spa"})
        blueprint["work_products"] = products
    validation = validate_blueprint(blueprint, {"schema_version": "0.1"})
    if validation.structure_status != "STRUCTURALLY_VALID":
        raise ValueError("Template blueprint is not structurally valid.")
    return blueprint
