"""First-party generation plugins. New production lines register here, not in factory.py."""

from __future__ import annotations

from typing import Any, Callable

ScaffoldHandler = Callable[..., Any]


def first_party_scaffolds() -> dict[str, ScaffoldHandler]:
    from .npm_wxt_extension import scaffold_npm_wxt_extension
    from .uv_fastapi_service import scaffold_uv_fastapi_service
    from .uv_mcp_server import scaffold_uv_mcp_server
    from .uv_notebook import scaffold_uv_notebook
    from .cargo_lib import scaffold_cargo_lib
    from .dotnet_wpf import scaffold_dotnet_wpf
    from .npm_vite_web import scaffold_npm_vite_web
    from .npm_vite_react import scaffold_npm_vite_react
    from .uv_typer_cli import scaffold_uv_typer_cli
    from .npm_next_web import scaffold_npm_next_web
    from .maturin_pyo3 import scaffold_maturin_pyo3
    from .dotnet_avalonia import scaffold_dotnet_avalonia
    from .npm_ts_library import scaffold_npm_ts_library
    from .npm_vite_vue import scaffold_npm_vite_vue
    from .dotnet_aspnet import scaffold_dotnet_aspnet
    from .npm_vscode_extension import scaffold_npm_vscode_extension
    from .npm_github_action import scaffold_npm_github_action
    from .uv_mkdocs import scaffold_uv_mkdocs
    from .npm_astro import scaffold_npm_astro
    from .npm_vite_svelte import scaffold_npm_vite_svelte
    from .cargo_cli import scaffold_cargo_cli
    from .cargo_axum import scaffold_cargo_axum
    from .uv_textual import scaffold_uv_textual
    from .uv_lambda import scaffold_uv_lambda
    from .npm_cloudflare_worker import scaffold_npm_cloudflare_worker
    from .npm_playwright_suite import scaffold_npm_playwright_suite
    from .npm_commander_cli import scaffold_npm_commander_cli
    from .npm_mcp_server import scaffold_npm_mcp_server
    from .uv_data_pipeline import scaffold_uv_data_pipeline
    from .uv_alembic import scaffold_uv_alembic
    from .npm_openapi_sdk import scaffold_npm_openapi_sdk
    from .uv_eval_harness import scaffold_uv_eval_harness
    from .uv_discord_bot import scaffold_uv_discord_bot
    from .uv_scraper import scaffold_uv_scraper
    from .npm_hono import scaffold_npm_hono
    from .npm_graphql import scaffold_npm_graphql
    from .uv_realtime import scaffold_uv_realtime
    from .uv_schema_contract import scaffold_uv_schema_contract
    from .uv_agent_workflow import scaffold_uv_agent_workflow
    from .npm_design_system import scaffold_npm_design_system
    from .uv_experiment import scaffold_uv_experiment
    from .npm_nest import scaffold_npm_nest
    from .uv_dbt import scaffold_uv_dbt
    from .uv_rag import scaffold_uv_rag
    from .uv_model_serving import scaffold_uv_model_serving
    from .uv_compose_stack import scaffold_uv_compose_stack
    from .dotnet_library import scaffold_dotnet_library
    from .uv_grpc import scaffold_uv_grpc
    from .uv_event_driven import scaffold_uv_event_driven
    from .uv_observability import scaffold_uv_observability
    from .opentofu_tf import scaffold_opentofu_tf
    from .go_scaffold import scaffold_go_cli, scaffold_go_lib
    from .java_scaffold import scaffold_java_cli, scaffold_java_lib
    from .kotlin_scaffold import scaffold_kotlin_cli, scaffold_kotlin_lib
    from .dart_scaffold import scaffold_dart_cli, scaffold_dart_lib
    from .swift_scaffold import scaffold_swift_cli, scaffold_swift_lib
    from .cpp_scaffold import scaffold_cpp_cli, scaffold_cpp_lib
    from .c_scaffold import scaffold_c_cli, scaffold_c_lib
    from .php_scaffold import scaffold_php_cli, scaffold_php_lib
    from .r_scaffold import scaffold_r_cli, scaffold_r_lib
    from .mobile_game_userscript import (
        scaffold_mobile_flutter,
        scaffold_mobile_kotlin,
        scaffold_mobile_swift,
        scaffold_game_bevy,
        scaffold_game_godot,
        scaffold_userscript_ts,
    )

    handlers = {
        "uv-mcp-server": scaffold_uv_mcp_server,
        "npm-wxt-extension": scaffold_npm_wxt_extension,
        "uv-fastapi-service": scaffold_uv_fastapi_service,
        "uv-notebook": scaffold_uv_notebook,
        "cargo-lib": scaffold_cargo_lib,
        "dotnet-wpf": scaffold_dotnet_wpf,
        "npm-vite-web": scaffold_npm_vite_web,
        "npm-vite-react": scaffold_npm_vite_react,
        "uv-typer-app": scaffold_uv_typer_cli,
        "npm-next-web": scaffold_npm_next_web,
        "maturin-pyo3": scaffold_maturin_pyo3,
        "dotnet-avalonia": scaffold_dotnet_avalonia,
        "npm-ts-library": scaffold_npm_ts_library,
        "npm-vite-vue": scaffold_npm_vite_vue,
        "dotnet-aspnet": scaffold_dotnet_aspnet,
        "npm-vscode-extension": scaffold_npm_vscode_extension,
        "npm-github-action": scaffold_npm_github_action,
        "uv-mkdocs": scaffold_uv_mkdocs,
        "npm-astro": scaffold_npm_astro,
        "npm-vite-svelte": scaffold_npm_vite_svelte,
        "cargo-cli": scaffold_cargo_cli,
        "cargo-axum": scaffold_cargo_axum,
        "uv-textual-tui": scaffold_uv_textual,
        "uv-lambda": scaffold_uv_lambda,
        "npm-cloudflare-worker": scaffold_npm_cloudflare_worker,
        "npm-playwright-suite": scaffold_npm_playwright_suite,
        "npm-commander-cli": scaffold_npm_commander_cli,
        "npm-mcp-server": scaffold_npm_mcp_server,
        "uv-data-pipeline": scaffold_uv_data_pipeline,
        "uv-alembic": scaffold_uv_alembic,
        "npm-openapi-sdk": scaffold_npm_openapi_sdk,
        "uv-eval-harness": scaffold_uv_eval_harness,
        "uv-discord-bot": scaffold_uv_discord_bot,
        "uv-scraper": scaffold_uv_scraper,
        "npm-hono": scaffold_npm_hono,
        "npm-graphql": scaffold_npm_graphql,
        "uv-realtime": scaffold_uv_realtime,
        "uv-schema-contract": scaffold_uv_schema_contract,
        "uv-agent-workflow": scaffold_uv_agent_workflow,
        "npm-design-system": scaffold_npm_design_system,
        "uv-experiment": scaffold_uv_experiment,
        "npm-nest": scaffold_npm_nest,
        "uv-dbt": scaffold_uv_dbt,
        "uv-rag": scaffold_uv_rag,
        "uv-model-serving": scaffold_uv_model_serving,
        "uv-compose-stack": scaffold_uv_compose_stack,
        "dotnet-library": scaffold_dotnet_library,
        "uv-grpc": scaffold_uv_grpc,
        "uv-event-driven": scaffold_uv_event_driven,
        "uv-observability": scaffold_uv_observability,
        "opentofu-tf": scaffold_opentofu_tf,
        # E1 language roots (cli + library)
        "go-cli": scaffold_go_cli,
        "go-lib": scaffold_go_lib,
        "java-cli": scaffold_java_cli,
        "java-lib": scaffold_java_lib,
        "kotlin-cli": scaffold_kotlin_cli,
        "kotlin-lib": scaffold_kotlin_lib,
        "dart-cli": scaffold_dart_cli,
        "dart-lib": scaffold_dart_lib,
        "swift-cli": scaffold_swift_cli,
        "swift-lib": scaffold_swift_lib,
        "cpp-cli": scaffold_cpp_cli,
        "cpp-lib": scaffold_cpp_lib,
        "c-cli": scaffold_c_cli,
        "c-lib": scaffold_c_lib,
        "php-cli": scaffold_php_cli,
        "php-lib": scaffold_php_lib,
        "r-cli": scaffold_r_cli,
        "r-lib": scaffold_r_lib,
        # E3 new car types
        "mobile-flutter": scaffold_mobile_flutter,
        "mobile-kotlin": scaffold_mobile_kotlin,
        "mobile-swift": scaffold_mobile_swift,
        "game-bevy": scaffold_game_bevy,
        "game-godot": scaffold_game_godot,
        "userscript-ts": scaffold_userscript_ts,
    }
    handlers.update(_load_user_scaffolds())
    return handlers


def _load_user_scaffolds() -> dict[str, ScaffoldHandler]:
    import importlib.util
    import os
    from pathlib import Path

    flag = os.environ.get("PROJECT_FACTORY_LOAD_USER_WAREHOUSE", "").strip().casefold()
    if flag in {"0", "false", "no"}:
        return {}
    explicit = os.environ.get("PROJECT_FACTORY_USER_WAREHOUSE", "").strip()
    if explicit:
        root = Path(explicit)
    elif flag in {"1", "true", "yes"}:
        root = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "ProjectFactory" / "user_warehouse"
    else:
        return {}
    plugin_dir = root / "plugins"
    if not plugin_dir.is_dir():
        return {}
    loaded: dict[str, ScaffoldHandler] = {}
    for path in sorted(plugin_dir.glob("*.py")):
        spec = importlib.util.spec_from_file_location(f"user_scaffold_{path.stem}", path)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception:
            continue
        recipe_id = str(getattr(module, "SCAFFOLD_ID", "") or "").strip()
        handler = getattr(module, "scaffold", None)
        if recipe_id and callable(handler):
            loaded[recipe_id] = handler
    return loaded
