"""First-party verification suite builders. Registry may select an id, not inject commands."""

from __future__ import annotations

from typing import Any, Callable

from ..verification import VerificationSuite

SuiteBuilder = Callable[[str, Any], VerificationSuite]


def first_party_suites() -> dict[str, SuiteBuilder]:
    from .browser_extension_wxt import build_browser_extension_wxt_suite
    from .python_http_service import build_python_http_service_suite
    from .python_mcp_server import build_python_mcp_server_suite
    from .python_notebook import build_python_notebook_suite
    from .rust_library import build_rust_library_suite
    from .csharp_desktop import build_csharp_desktop_suite
    from .typescript_web_ui import build_typescript_web_ui_suite
    from .typescript_web_ssr import build_typescript_web_ssr_suite
    from .python_native_extension import build_python_native_extension_suite
    from .csharp_desktop_avalonia import build_csharp_desktop_avalonia_suite
    from .typescript_library import build_typescript_library_suite
    from .csharp_http_service import build_csharp_http_service_suite
    from .vscode_extension import build_vscode_extension_suite
    from .github_action import build_github_action_suite
    from .python_docs_site import build_python_docs_site_suite
    from .typescript_static_astro import build_typescript_static_astro_suite
    from .rust_cli import build_rust_cli_suite
    from .rust_http_service import build_rust_http_service_suite
    from .python_tui import build_python_tui_suite
    from .python_lambda import build_python_lambda_suite
    from .cloudflare_worker import build_cloudflare_worker_suite
    from .playwright_test_suite import build_playwright_test_suite
    from .typescript_cli import build_typescript_cli_suite
    from .typescript_mcp_server import build_typescript_mcp_server_suite
    from .python_data_pipeline import build_python_data_pipeline_suite
    from .python_schema_migration import build_python_schema_migration_suite
    from .typescript_generated_sdk import build_typescript_generated_sdk_suite
    from .python_eval_harness import build_python_eval_harness_suite
    from .python_bot import build_python_bot_suite
    from .python_scraper import build_python_scraper_suite
    from .typescript_http_hono import build_typescript_http_hono_suite
    from .typescript_graphql import build_typescript_graphql_suite
    from .python_realtime import build_python_realtime_suite
    from .python_schema_contract import build_python_schema_contract_suite
    from .python_agent_workflow import build_python_agent_workflow_suite
    from .typescript_design_system import build_typescript_design_system_suite
    from .python_experiment import build_python_experiment_suite
    from .typescript_http_nest import build_typescript_http_nest_suite
    from .python_analytics_dbt import build_python_analytics_dbt_suite
    from .python_rag import build_python_rag_suite
    from .python_model_serving import build_python_model_serving_suite
    from .python_container_stack import build_python_container_stack_suite
    from .csharp_library import build_csharp_library_suite
    from .python_grpc import build_python_grpc_suite
    from .python_event_driven import build_python_event_driven_suite
    from .python_observability import build_python_observability_suite
    from .iac_opentofu import build_iac_opentofu_suite
    from .lang_cli_suites import (
        build_go_cli_suite,
        build_java_cli_suite,
        build_kotlin_cli_suite,
        build_dart_cli_suite,
        build_swift_cli_suite,
        build_cpp_cli_suite,
        build_c_cli_suite,
        build_php_cli_suite,
        build_r_cli_suite,
    )
    from .lang_lib_suites import (
        build_go_lib_suite,
        build_java_lib_suite,
        build_kotlin_lib_suite,
        build_dart_lib_suite,
        build_swift_lib_suite,
        build_cpp_lib_suite,
        build_c_lib_suite,
        build_php_lib_suite,
        build_r_lib_suite,
    )
    from .mobile_game_userscript_suites import (
        build_flutter_mobile_suite,
        build_kotlin_mobile_suite,
        build_swift_mobile_suite,
        build_bevy_game_suite,
        build_godot_game_suite,
        build_typescript_userscript_suite,
    )

    return {
        "python-mcp-server": build_python_mcp_server_suite,
        "browser-extension-wxt": build_browser_extension_wxt_suite,
        "python-http-service": build_python_http_service_suite,
        "python-notebook": build_python_notebook_suite,
        "rust-library": build_rust_library_suite,
        "csharp-desktop": build_csharp_desktop_suite,
        "typescript-web-ui": build_typescript_web_ui_suite,
        "typescript-web-ssr": build_typescript_web_ssr_suite,
        "python-native-extension": build_python_native_extension_suite,
        "csharp-desktop-avalonia": build_csharp_desktop_avalonia_suite,
        "typescript-library": build_typescript_library_suite,
        "csharp-http-service": build_csharp_http_service_suite,
        "vscode-extension": build_vscode_extension_suite,
        "github-action": build_github_action_suite,
        "python-docs-site": build_python_docs_site_suite,
        "typescript-static-astro": build_typescript_static_astro_suite,
        "rust-cli": build_rust_cli_suite,
        "rust-http-service": build_rust_http_service_suite,
        "python-tui": build_python_tui_suite,
        "python-lambda": build_python_lambda_suite,
        "cloudflare-worker": build_cloudflare_worker_suite,
        "playwright-test-suite": build_playwright_test_suite,
        "typescript-cli": build_typescript_cli_suite,
        "typescript-mcp-server": build_typescript_mcp_server_suite,
        "python-data-pipeline": build_python_data_pipeline_suite,
        "python-schema-migration": build_python_schema_migration_suite,
        "typescript-generated-sdk": build_typescript_generated_sdk_suite,
        "python-eval-harness": build_python_eval_harness_suite,
        "python-bot": build_python_bot_suite,
        "python-scraper": build_python_scraper_suite,
        "typescript-http-hono": build_typescript_http_hono_suite,
        "typescript-graphql": build_typescript_graphql_suite,
        "python-realtime": build_python_realtime_suite,
        "python-schema-contract": build_python_schema_contract_suite,
        "python-agent-workflow": build_python_agent_workflow_suite,
        "typescript-design-system": build_typescript_design_system_suite,
        "python-experiment": build_python_experiment_suite,
        "typescript-http-nest": build_typescript_http_nest_suite,
        "python-analytics-dbt": build_python_analytics_dbt_suite,
        "python-rag": build_python_rag_suite,
        "python-model-serving": build_python_model_serving_suite,
        "python-container-stack": build_python_container_stack_suite,
        "csharp-library": build_csharp_library_suite,
        "python-grpc": build_python_grpc_suite,
        "python-event-driven": build_python_event_driven_suite,
        "python-observability": build_python_observability_suite,
        "iac-opentofu": build_iac_opentofu_suite,
        # E1 language roots (cli + library)
        "go-cli": build_go_cli_suite,
        "go-lib": build_go_lib_suite,
        "java-cli": build_java_cli_suite,
        "java-lib": build_java_lib_suite,
        "kotlin-cli": build_kotlin_cli_suite,
        "kotlin-lib": build_kotlin_lib_suite,
        "dart-cli": build_dart_cli_suite,
        "dart-lib": build_dart_lib_suite,
        "swift-cli": build_swift_cli_suite,
        "swift-lib": build_swift_lib_suite,
        "cpp-cli": build_cpp_cli_suite,
        "cpp-lib": build_cpp_lib_suite,
        "c-cli": build_c_cli_suite,
        "c-lib": build_c_lib_suite,
        "php-cli": build_php_cli_suite,
        "php-lib": build_php_lib_suite,
        "r-cli": build_r_cli_suite,
        "r-lib": build_r_lib_suite,
        # E3 new car types
        "flutter-mobile": build_flutter_mobile_suite,
        "kotlin-mobile": build_kotlin_mobile_suite,
        "swift-mobile": build_swift_mobile_suite,
        "bevy-game": build_bevy_game_suite,
        "godot-game": build_godot_game_suite,
        "typescript-userscript": build_typescript_userscript_suite,
    }
