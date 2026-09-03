"""Repo assembly plans. Topology, not a welded fullstack Profile name."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .registry import RegistryError, load_registry, select_profile


WEB_KINDS = frozenset({"web-ui", "web-spa", "web-ssr"})
SERVICE_KINDS = frozenset({"service", "http-service"})


@dataclass(frozen=True)
class AssemblyOptions:
    scaffold: bool = True
    verification: bool = True
    overlay: bool = True
    harness: bool = True
    readme: bool = True
    harness_ids: tuple[str, ...] | None = None
    with_compose: bool = False  # C04: http-service optional compose overlay (Postgres drawing, docker up UNVERIFIED)

    def nothing_selected(self) -> bool:
        return not any((self.scaffold, self.verification, self.overlay, self.harness, self.readme))


@dataclass(frozen=True)
class PackagePlan:
    directory: str
    profile_id: str
    project_name: str


@dataclass(frozen=True)
class AssemblyPlan:
    mode: str
    packages: tuple[PackagePlan, ...] = ()
    reason: str = ""
    profile_id: str = ""


def default_options() -> AssemblyOptions:
    return AssemblyOptions()


def _tech(blueprint: dict[str, Any]) -> set[str]:
    return {str(item) for item in blueprint.get("technology", {}).get("required", [])}


def _web_profile_id(tech: set[str]) -> str:
    if "react" in tech:
        return "typescript-web-react"
    if "vue" in tech:
        return "typescript-web-vue"
    if "svelte" in tech:
        return "typescript-web-svelte"
    if "nextjs" in tech:
        return "typescript-web-ssr"
    return "typescript-web-ui"


def _api_profile_id(tech: set[str]) -> str:
    if "csharp" in tech:
        return "csharp-http-service"
    if "rust" in tech or "axum" in tech:
        return "rust-http-service"
    if "nestjs" in tech:
        return "typescript-http-nest"
    if "hono" in tech:
        return "typescript-http-hono"
    return "python-http-service"


def plan_assembly(blueprint: dict[str, Any], project_name: str, registry: Any | None = None) -> AssemblyPlan:
    registry = registry or load_registry()
    products = {str(item.get("kind")) for item in blueprint.get("work_products", [])}
    web = products & WEB_KINDS
    service = products & SERVICE_KINDS
    if web and service:
        tech = _tech(blueprint)
        # A frontend-backend split assembles EXACTLY ONE web product + ONE service product.
        # Anything beyond that (a third product like notebook, or a second web/service) would
        # otherwise be silently dropped by the early return below — which contradicts the very
        # guardrail this module advertises ("Refusing to silently drop work products"). So refuse
        # explicitly and name what would be dropped. Same discipline as the single-product branch.
        chosen_web = next(iter(web))
        chosen_service = next(iter(service))
        dropped = set(products)
        dropped.discard(chosen_web)
        dropped.discard(chosen_service)
        if dropped:
            return AssemblyPlan(
                mode="reject",
                reason=(
                    "Refusing to silently drop work products "
                    + ", ".join(sorted(dropped))
                    + ". A frontend-backend split assembles exactly one web product + one service product. "
                    + "Generate one product, or assemble exactly one http-service + one web-spa/web-ui/web-ssr as frontend-backend-split."
                ),
                profile_id="frontend-backend-split",
            )
        api_id = _api_profile_id(tech)
        web_id = _web_profile_id(tech)
        return AssemblyPlan(
            mode="split",
            packages=(
                PackagePlan("api", api_id, f"{project_name}-api"),
                PackagePlan("web", web_id, f"{project_name}-web"),
            ),
            profile_id="frontend-backend-split",
        )
    try:
        selected = select_profile(blueprint, registry)
    except RegistryError as exc:
        return AssemblyPlan(mode="reject", reason=str(exc))
    covered = set(selected.match.get("work_products_any", ()) or ())
    leftover = {item for item in products if item not in covered and item not in {"unspecified", "application"}}
    if leftover <= {"service", "http-service"} and (products - leftover):
        leftover = set()
    if leftover and len(products) > 1:
        return AssemblyPlan(
            mode="reject",
            reason=(
                "Refusing to silently drop work products "
                + ", ".join(sorted(leftover))
                + ". Generate one product, or assemble http-service + web-spa as frontend-backend-split."
            ),
            profile_id=selected.id,
        )
    return AssemblyPlan(mode="single", profile_id=selected.id)


def profile_next_steps(profile_id: str) -> str:
    catalog = {
        "python-http-service": "Add domain routes next to `/health` in `src/{pkg}/routers/`. Keep `TestClient` green. Live port binding stays UNVERIFIED. Optional `compose.yaml` (Postgres drawing) via `--with-compose`, `docker up` stays UNVERIFIED.",
        "csharp-http-service": "Add ASP.NET controllers next to `/health`. Keep `dotnet build` green. Live port stays UNVERIFIED. Optional `compose.yaml` via `--with-compose`.",
        "typescript-http-nest": "Add Nest `modules/controllers` with `TestingModule`. Keep `npm run build` green. Live port stays UNVERIFIED. Uses @nestjs 10.4.15, not Hono. Optional compose via `--with-compose`.",
        "typescript-http-hono": "Add Hono routes via `app.request`. Keep `npm run build` green. Live port stays UNVERIFIED. Uses hono 4.7.4. Optional compose via `--with-compose`.",
        "rust-http-service": "Add Axum handler on `axum 0.8.4` with `oneshot`. Keep `cargo test` green. No tokio/net binding. Keep `clap` color off. Optional compose via `--with-compose`.",
        "python-grpc": "Implement domain RPCs on the in-process gRPC servicer. Keep `grpc servicer` unit green. Port binding stays UNVERIFIED.",
        "typescript-graphql": "Add GraphQL typeDefs/resolvers and `execute` tests. Keep `npm run build` green. HTTP listener stays UNVERIFIED.",
        "python-realtime": "Add Starlette `WebSocket` handler and `TestClient` tests. Keep `python-realtime` green. Live port stays UNVERIFIED.",
        "python-cli": "Implement `src/{pkg}/main.py` argparse command. Keep `unittest` mandatory and `pytest 8.3.5` additive green.",
        "python-cli-typer": "Implement `typer 0.15.2` command (argparse still graduates). Keep both gates green. Body is Typer, not argparse.",
        "rust-cli": "Implement `clap 4.5.32` command (color off to avoid windows-sys). Keep `cargo test` green.",
        "typescript-cli": "Implement `commander 12.1.0` command. Keep `npm test` green. Publish stays UNVERIFIED.",
        "python-library": "Implement public API in `src/{pkg}/`. Keep `import` + `unittest` green. Add `pytest` if you want.",
        "typescript-library": "Implement `src/index.ts` exports. Keep `tsc` + `npm pack` green.",
        "node-library": "Implement JS library entry. Keep `node --test` green.",
        "csharp-library": "Implement classlib public API. Keep `dotnet build`/`dotnet test xunit` green. nuget.org stays UNVERIFIED.",
        "rust-library": "Implement `cargo test` lib. Keep `cargo test` green. crates.io publish stays UNVERIFIED.",
        "browser-extension-js": "Edit `manifest.json` + `src/` hand-written MV3. Keep `npm run build` green. Real browser runtime stays UNVERIFIED.",
        "browser-extension-wxt": "Edit `wxt.config.ts` + `entrypoints/`. Keep `wxt build` green. Real browser stays UNVERIFIED. JS requests stay on hand-written line.",
        "python-mcp-server": "Add `@mcp.tool/@mcp.resource/@mcp.prompt` in `src/{pkg}/server.py`. Tools: `echo_purpose`, resource `scaffold://status`, prompt `introduce`. Keep in-memory `Client` test green. Real Host: run `python scripts/verify_real_host.py` (developer-executed; Factory is not an MCP Host).",
        "typescript-mcp-server": "Add `server.tool('echo_purpose')` in `src/server.ts`. Keep `InMemoryTransport` test green. Real Host stays UNVERIFIED. SDK 1.12.1.",
        "typescript-web-ui": "Replace Vite `src/` UI. Keep `vite 6.3.5 build` green. `typescript 5.8.3`. Browser runtime stays UNVERIFIED.",
        "typescript-web-react": "Replace React `App` (`react 18.3.1`). Keep Vite build green. Runtime stays UNVERIFIED.",
        "typescript-web-vue": "Replace Vue `App.vue` (`vue 3.5.13`). Keep Vite build green. Runtime stays UNVERIFIED. Not a new kind.",
        "typescript-web-svelte": "Replace Svelte `App.svelte` (`svelte 5.16.0`). Keep Vite build green. Not a new kind.",
        "typescript-web-ssr": "Replace Next page (`next 15.2.4`). Keep `npm run build` green. `dev/start` stays UNVERIFIED.",
        "typescript-static-astro": "Add `src/pages/` Astro `5.5.5 build`. Keep build green. Preview stays UNVERIFIED.",
        "csharp-desktop": "Add WPF window in `src/`. Keep `dotnet build` green. Window display stays UNVERIFIED. Self-contained not required.",
        "csharp-desktop-avalonia": "Add Avalonia `11.2.8` view (`net9.0`). Keep `dotnet build` green. Window display stays UNVERIFIED.",
        "python-notebook": "Edit `notebook.ipynb` cells. Keep `nb execute` green. Provenance + params preserved. JupyterLab runtime stays UNVERIFIED.",
        "python-experiment": "Write `params.json → results`. Keep unit green. Training stays UNVERIFIED (not a notebook).",
        "cloudflare-worker": "Edit `wrangler.toml` + `src/worker.ts`. Keep `tsc` green. `deploy` stays UNVERIFIED; no wrangler runtime required.",
        "python-lambda": "Implement `handler(event,context)→200` in `src/`. Keep in-process test green. AWS deploy stays UNVERIFIED.",
        "github-action": "Edit `action.yml` `Node 20` entry. Keep `npm pack` green. Runner `UNVERIFIED`.",
        "python-docs-site": "Add `mkdocs 1.6.1 + material 9.6.11` docs. Keep `mkdocs build` green. `serve` stays UNVERIFIED.",
        "python-tui": "Implement Textual `2.1.2` app in `src/`. Keep import green. Interactive TUI stays UNVERIFIED.",
        "python-data-pipeline": "Add `transform()` in `src/`. Keep unit green. Real schedule (cron/Dagster) stays UNVERIFIED.",
        "python-analytics-dbt": "Add `models/` `dbt-core 1.9.4 + duckdb`. Keep `dbt parse` green. Warehouse stays UNVERIFIED.",
        "python-schema-migration": "Add `alembic 1.14.1` migration. Keep `upgrade head` on SQLite green. Postgres stays UNVERIFIED.",
        "python-native-extension": "Edit `src/` PyO3 `maturin 1.8.3`. Keep `maturin build` green. Import stays UNVERIFIED.",
        "python-observability": "Add `SDK 1.31.1` `InMemoryExporter` span. Keep unit green. Collector stays UNVERIFIED.",
        "python-event-driven": "Add `handle(event)` in-process. Keep unit green. Broker: run `python scripts/verify_real_broker.py` (local in-process broker; wire your real Kafka/RabbitMQ/SQS yourself). Distinct from http-service+celery.",
        "python-container-stack": "Edit `compose.yaml` overlay. Keep file exists green. `docker up` stays UNVERIFIED.",
        "python-rag": "Add `retrieve(query)` in-memory. Keep unit green. Vector DB: run `python scripts/verify_real_retriever.py` over `fixtures/docs.json` (in-process retrieval); wire your real vector store yourself.",
        "python-model-serving": "Add `predict(payload)` stub. Keep unit green. GPU/weights stay UNVERIFIED.",
        "python-eval-harness": "Add `eval()` scoring against fixtures. Keep unit green. Training/fetch stays UNVERIFIED.",
        "python-bot": "Register `discord.py 2.4.0` commands in `src/`. Keep registration unit green. Gateway stays UNVERIFIED.",
        "python-scraper": "Add `beautifulsoup4` parse of local HTML. Keep unit green. Live crawl/Scrapy stays UNVERIFIED.",
        "python-schema-contract": "Freeze `openapi.yaml`. Keep lint green. Live contract verification stays UNVERIFIED.",
        "python-agent-workflow": "Add `step graph` in `src/`. Keep unit green. Live LLM stays UNVERIFIED. Not a Factory Host.",
        "typescript-design-system": "Add `tokens` + CSS. Keep `tsc` green. Storybook stays UNVERIFIED.",
        "typescript-generated-sdk": "Add `openapi-typescript 7.6.1` client. Keep `tsc` green. Live upstream stays UNVERIFIED.",
        "playwright-test-suite": "Add `tests/` `@playwright/test 1.49.1`. Uses system Chrome/Edge; if missing, UNVERIFIED. Does not download browser.",
        "vscode-extension": "Edit `src/extension.ts` + `package.json`. Keep `vsce package` green. Marketplace publish stays UNVERIFIED.",
        "frontend-backend-split": "Work in `api/` and `web/` separately. Each has its own language root / verification. Do not weld into `python-fastapi-react-postgres`.",
    }
    return catalog.get(
        profile_id,
        "Implement domain behavior in source you own. Do not rewrite Factory verification commands to make a gate pass. Keep evidence under `.project/evidence/`.",
    )


def render_profile_skill(project_name: str, profile_id: str, factory_version: str) -> str:
    return (
        f"---\nname: {profile_id}\n"
        f"description: How to work in this Factory-generated {profile_id} project.\n---\n\n"
        f"# {profile_id}\n\n"
        f"Project `{project_name}` uses profile `{profile_id}` (overlay {factory_version}).\n\n"
        f"## Next\n\n{profile_next_steps(profile_id)}\n\n"
        "## Ownership\n\n"
        "You own source under the language root. Factory owns overlay, lock, and harness adapters.\n"
        "Harness files must stay byte-identical to `.project/contract/agent-contract.md`.\n"
    )


# Q4-③: profiles that ship a developer-executed real-host/broker verification script.
REAL_HOST_SCRIPT: dict[str, str] = {
    "python-mcp-server": "python scripts/verify_real_host.py",
    "python-event-driven": "python scripts/verify_real_broker.py",
    "python-rag": "python scripts/verify_real_retriever.py",
}


def render_coding_workflow(
    project_name: str,
    profile_id: str,
    *,
    verification_commands: list[list[str]] | None = None,
    real_host_script: str | None = None,
) -> str:
    """Q4-①: a concrete, agent-discoverable coding runbook.

    Unlike the per-line SKILL.md (meta/ownership), this is a step-by-step workflow a
    coding agent can follow to implement domain behavior without guessing. Written at the
    project root as `WORKFLOW.md` (ungated, like README) so the project is caught by an
    agent out of the box even when harness materialization is disabled.
    """
    commands = verification_commands or []
    cmd_block = "\n".join(f"```bash\n{' '.join(c)}\n```" for c in commands) or "```bash\n# (see README.md verification section)\n```"
    if real_host_script:
        real_host_block = (
            "\n\n## Real-host / broker check (developer-executed)\n\n"
            "Factory does not run external runtimes. Verify the real integration yourself:\n\n"
            f"```bash\n{real_host_script}\n```\n\n"
            "Expected: prints `REAL HOST OK` / `REAL BROKER OK` / `REAL RETRIEVER OK`.\n"
        )
    else:
        real_host_block = (
            "\n\n## Real-host check\n\n"
            "This profile's external runtime (live port / browser / gateway / deploy) is not run by Factory. "
            "Implement domain behavior, then verify against your real environment.\n"
        )
    return f'''# Coding Workflow — {project_name}

You are a coding agent working in a Factory-generated `{profile_id}` scaffold.

## Bootstrap (read first)

- This is a **claim-scoped scaffold**. Before treating any behavior as verified, inspect
  `.project/evidence/generation-verification.json`. The Factory has **not** implemented domain behavior.
- You own source under the language root. Factory owns the overlay, `project.lock.json`, and harness adapters
  (`.project/contract/agent-contract.md`, `AGENTS.md`, `CLAUDE.md`). Do not edit harness files by hand —
  they are byte-identical copies of the canonical contract.

## Repeat per feature

1. Read the canonical contract: `.project/contract/agent-contract.md` (mirrored to `AGENTS.md` / `CLAUDE.md`).
2. Implement domain behavior in the language root (`src/<pkg>/`). Prefer native ecosystem tooling.
3. Keep the required verification green:

{cmd_block}
{real_host_block}
4. Attach execution evidence under `.project/evidence/`. Do **not** claim completion from an agent statement alone.

## Next steps for this profile

{profile_next_steps(profile_id)}

## Engineering discipline (non-negotiable)

- Do not rewrite Factory verification commands to make a gate pass.
- Do not introduce a Runner, multi-agent team, or new framework unless the task demonstrates a need.
- Preserve the original Blueprint and Project Lock as provenance.
- Destructive or irreversible operations require an explicit recovery plan.
'''
