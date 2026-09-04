from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from project_factory.factory import (
    FACTORY_STAGE,
    FACTORY_VERSION,
    FactoryError,
    derive_execution_decision,
    generate_project,
    resolve_profile,
    restore_verify_project_zip,
    verify_project_manifest,
)
from project_factory.normalizer import normalize_requirement
from project_factory.decision import IntentSnapshot, RepositoryState


CASES = {
    "python-cli": (
        "json-batch-cli",
        "做一个 Python 命令行工具，批量读取一个目录里的 JSON 并转换格式。不能覆盖原始文件。",
        "uv",
    ),
    "python-cli-typer": (
        "json-batch-typer",
        "做一个带 Typer 的 Python CLI。",
        "uv",
    ),
    "python-native-extension": (
        "probe-ext",
        "用 maturin 给 Python 写 Rust 扩展。",
        "cargo",
    ),
    "python-library": (
        "text-normalizer-lib",
        "做一个 Python library，提供可复用的文本标准化能力，长期维护。",
        "uv",
    ),
    "node-library": (
        "string-tools-js",
        "做一个 JavaScript library，提供可复用的字符串处理能力，长期维护。",
        "npm",
    ),
    "browser-extension-js": (
        "cross-browser-helper",
        "做一个 JavaScript 浏览器扩展，必须支持 Chrome 和 Firefox，先建立可靠项目基地。",
        "npm",
    ),
    "python-mcp-server": (
        "echo-mcp-server",
        "做一个 Python MCP 服务器，向外部 Agent 暴露工具、资源和提示词。",
        "uv",
    ),
    "browser-extension-wxt": (
        "cross-browser-wxt",
        "做一个 TypeScript 浏览器扩展，必须支持 Chrome 和 Firefox，先建立可靠项目基地。",
        "npm",
    ),
    "python-http-service": (
        "health-api",
        "做一个 Python 后端服务，提供 HTTP API。",
        "uv",
    ),
    "python-notebook": (
        "repro-notebook",
        "做一个 Python Jupyter 研究笔记本，保存实验参数和数据出处。",
        "uv",
    ),
    "rust-library": (
        "string-tools-rs",
        "做一个 Rust crate，提供可复用的字符串处理能力，长期维护。",
        "cargo",
    ),
    "csharp-desktop": (
        "tray-helper-wpf",
        "做一个 C# WPF 桌面应用。",
        "dotnet",
    ),
    "csharp-desktop-avalonia": (
        "tray-helper-avalonia",
        "做一个 Avalonia 跨平台桌面应用。",
        "dotnet",
    ),
    "typescript-web-ui": (
        "status-board",
        "做一个 TypeScript 前端网页应用。",
        "npm",
    ),
    "typescript-web-react": (
        "status-board-react",
        "做一个 React 单页应用。",
        "npm",
    ),
    "typescript-web-ssr": (
        "status-board-next",
        "做一个 Next.js 网站。",
        "npm",
    ),
    "typescript-library": (
        "string-tools-ts",
        "做一个 TypeScript 库。",
        "npm",
    ),
    "typescript-web-vue": (
        "status-board-vue",
        "做一个 Vue 单页应用。",
        "npm",
    ),
    "csharp-http-service": (
        "health-api-aspnet",
        "做一个 ASP.NET Core Web API。",
        "dotnet",
    ),
    "vscode-extension": (
        "hello-vscode",
        "做一个 VS Code 插件。",
        "npm",
    ),
    "github-action": (
        "hello-gha",
        "做一个 GitHub Action。",
        "npm",
    ),
    "python-docs-site": (
        "docs-home",
        "做一个文档站。",
        "uv",
    ),
    "typescript-static-astro": (
        "static-home",
        "做一个 Astro 静态站。",
        "npm",
    ),
    "typescript-web-svelte": (
        "status-board-svelte",
        "做一个 Svelte 单页应用。",
        "npm",
    ),
    "rust-cli": (
        "hello-clap",
        "做一个 Rust clap CLI。",
        "cargo",
    ),
    "rust-http-service": (
        "health-api-axum",
        "做一个 Axum HTTP 服务。",
        "cargo",
    ),
    "python-tui": (
        "status-tui",
        "做一个 Python TUI。",
        "uv",
    ),
    "python-lambda": (
        "hello-lambda",
        "做一个 AWS Lambda。",
        "uv",
    ),
    "cloudflare-worker": (
        "hello-worker",
        "做一个 Cloudflare Worker。",
        "npm",
    ),
    "playwright-test-suite": (
        "e2e-suite",
        "做一个独立 Playwright 仓库。",
        "npm",
    ),
    "typescript-cli": (
        "hello-commander",
        "做一个 Commander CLI。",
        "npm",
    ),
    "typescript-mcp-server": (
        "echo-ts-mcp",
        "做一个 TypeScript MCP 服务器。",
        "npm",
    ),
    "python-data-pipeline": (
        "nightly-etl",
        "做一个定时 ETL。",
        "uv",
    ),
    "python-schema-migration": (
        "schema-home",
        "做一个独立的数据库 migration 仓库。",
        "uv",
    ),
    "typescript-generated-sdk": (
        "health-client",
        "从 OpenAPI 生成 TypeScript 客户端。",
        "npm",
    ),
    "python-eval-harness": (
        "score-home",
        "做一个评测仓。",
        "uv",
    ),
    "python-bot": (
        "hello-bot",
        "做一个 Discord 机器人。",
        "uv",
    ),
    "python-scraper": (
        "page-scraper",
        "做一个爬虫。",
        "uv",
    ),
    "typescript-http-hono": (
        "health-hono",
        "做一个 Hono 边缘 API。",
        "npm",
    ),
    "typescript-graphql": (
        "status-graphql",
        "做一个 GraphQL API。",
        "npm",
    ),
    "python-realtime": (
        "status-ws",
        "做一个 WebSocket 实时服务。",
        "uv",
    ),
    "python-schema-contract": (
        "api-contract",
        "做一个 OpenAPI 合同仓。",
        "uv",
    ),
    "python-agent-workflow": (
        "echo-workflow",
        "做一个用户侧的 agent 工作流项目。",
        "uv",
    ),
    "typescript-design-system": (
        "token-kit",
        "做一个设计系统。",
        "npm",
    ),
    "python-experiment": (
        "seeded-run",
        "做一个可复现实验仓。",
        "uv",
    ),
    "typescript-http-nest": (
        "health-nest",
        "做一个 NestJS 微服务。",
        "npm",
    ),
    "python-analytics-dbt": (
        "metrics-dbt",
        "做一个 dbt 项目。",
        "uv",
    ),
    "python-rag": (
        "doc-rag",
        "做一个 RAG service。",
        "uv",
    ),
    "python-model-serving": (
        "score-serve",
        "做一个模型推理服务。",
        "uv",
    ),
    "python-container-stack": (
        "compose-home",
        "做一个 Docker Compose 栈仓。",
        "uv",
    ),
    "csharp-library": (
        "string-tools-cs",
        "做一个 C# library，提供可复用的字符串处理能力，长期维护。",
        "dotnet",
    ),
    "python-grpc": (
        "health-grpc",
        "做一个 gRPC 服务。",
        "uv",
    ),
    "python-event-driven": (
        "queue-consumer",
        "做一个纯消费者，没有 HTTP。",
        "uv",
    ),
    "python-observability": (
        "otel-probe",
        "做一个 OpenTelemetry collector 配置/探针项目。",
        "uv",
    ),
}


class P3DecisionTests(unittest.TestCase):
    def test_minimal_formula_keeps_runner_and_reviewer_off_for_all_profiles(self) -> None:
        for expected_profile, (_, requirement, _) in CASES.items():
            with self.subTest(profile=expected_profile):
                normalized = normalize_requirement(requirement)
                self.assertEqual(normalized.validation.readiness_status, "USABLE")
                profile = resolve_profile(normalized.blueprint)
                self.assertEqual(profile.profile_id, expected_profile)
                decision = derive_execution_decision(normalized.blueprint)
                self.assertEqual(decision.materialization, "minimal")
                self.assertEqual(decision.agent_topology, "single-main-agent")
                self.assertEqual(decision.parallelism, 1)
                self.assertFalse(decision.runner_required)
                self.assertFalse(decision.reviewer_required)

    def test_unsupported_profile_does_not_silently_fall_back(self) -> None:
        # TypeScript browser extensions are owned (browser-extension-wxt).
        # Rust GUI is still unsupported: iced does not link on this Windows GNU host.
        blueprint = {
            "schema_version": "0.1",
            "project": {"purpose": "A native desktop shell that is not Electron."},
            "work_products": [{"kind": "desktop-app"}],
            "technology": {"required": ["rust"]},
        }
        with self.assertRaises(FactoryError):
            resolve_profile(blueprint)
        with self.assertRaises(FactoryError):
            derive_execution_decision(blueprint)


# Integration smoke tests that drive a real external toolchain while the
# blueprint is generated (npm install / cargo test / dotnet build, etc.).
# CI only guarantees Python + uv, so these are skipped there instead of
# failing; the local dev matrix (uv, npm, cargo, dotnet, maturin) still
# exercises every blueprint end to end.
SMOKE_TOOLCHAIN: dict[str, str] = {
    "test_wxt_extension_generate_verify_and_restore_smoke": "npm",
    "test_vite_web_ui_generate_verify_and_restore_smoke": "npm",
    "test_vite_react_body_generate_verify_and_restore_smoke": "npm",
    "test_next_ssr_generate_verify_and_restore_smoke": "npm",
    "test_typescript_library_generate_verify_and_restore_smoke": "npm",
    "test_vue_web_body_generate_verify_and_restore_smoke": "npm",
    "test_vscode_extension_generate_verify_and_restore_smoke": "npm",
    "test_github_action_generate_verify_and_restore_smoke": "npm",
    "test_astro_static_site_generate_verify_and_restore_smoke": "npm",
    "test_svelte_body_generate_verify_and_restore_smoke": "npm",
    "test_cloudflare_worker_generate_verify_and_restore_smoke": "npm",
    "test_playwright_suite_generate_verify_and_restore_smoke": "npm",
    "test_commander_cli_generate_verify_and_restore_smoke": "npm",
    "test_typescript_mcp_generate_verify_and_restore_smoke": "npm",
    "test_openapi_sdk_generate_verify_and_restore_smoke": "npm",
    "test_hono_service_generate_verify_and_restore_smoke": "npm",
    "test_graphql_generate_verify_and_restore_smoke": "npm",
    "test_design_system_generate_verify_and_restore_smoke": "npm",
    "test_nest_service_generate_verify_and_restore_smoke": "npm",
    "test_rust_library_generate_verify_and_restore_smoke": "cargo",
    "test_rust_cli_generate_verify_and_restore_smoke": "cargo",
    "test_axum_service_generate_verify_and_restore_smoke": "cargo",
    "test_wpf_desktop_generate_verify_and_restore_smoke": "dotnet",
    "test_avalonia_desktop_generate_verify_and_restore_smoke": "dotnet",
    "test_aspnet_service_generate_verify_and_restore_smoke": "dotnet",
    "test_csharp_library_generate_verify_and_restore_smoke": "dotnet",
}


class P3GenerationIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        tool = SMOKE_TOOLCHAIN.get(self._testMethodName)
        if tool is None:
            return
        if os.environ.get("MCV_FACTORY_CI") == "1":
            # CI guarantees only Python + uv; Windows runners happen to ship
            # node/cargo/dotnet too, but those system toolchains are not the
            # pinned versions this harness validates against. The full local
            # dev matrix exercises every blueprint end to end.
            self.skipTest("external-toolchain smoke suites run on the local dev matrix, not CI")
        if shutil.which(tool) is None:
            self.skipTest(f"{tool} toolchain is required to build this blueprint")

    def test_python_cli_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "python-cli"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertTrue(result.project_root.is_dir())
            self.assertTrue(result.project_zip.is_file())
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)

            serialized_blueprint = json.dumps(result.blueprint, ensure_ascii=False).casefold()
            for forbidden in ("provider", "runner", "dagu", "aionui", "codex", "claude", "copier", "spec-kit"):
                self.assertNotIn(forbidden, serialized_blueprint)

            lock = json.loads((result.project_root / "project.lock.json").read_text(encoding="utf-8"))
            self.assertEqual(lock["factory"]["version"], FACTORY_VERSION)
            self.assertEqual(lock["factory"]["stage"], FACTORY_STAGE)
            self.assertEqual(lock["semantic_intake"]["adapter"]["id"], "deterministic-baseline")
            self.assertEqual(lock["formula"]["id"], "baseline-engineering")
            self.assertEqual(lock["policies"][0]["id"], "safe-defaults")
            self.assertEqual(lock["decision_context"]["intent"]["kind"], "bootstrap")
            self.assertEqual(lock["profile"]["id"], expected_profile)
            provider_lock = lock["providers"]["project_scaffolding"]
            self.assertEqual(provider_lock["id"], provider_id)
            self.assertFalse(provider_lock["upstream_source_modified"])
            self.assertFalse(lock["execution_decision"]["runner_required"])

            manifest_ok, failures = verify_project_manifest(result.project_root)
            self.assertTrue(manifest_ok, failures)
            for forbidden_dir in (".venv", "dist", "node_modules", ".git"):
                self.assertFalse((result.project_root / forbidden_dir).exists())

            with zipfile.ZipFile(result.project_zip) as archive:
                self.assertIsNone(archive.testzip())
                names = archive.namelist()
                self.assertIn(f"{project_name}/AGENTS.md", names)
                self.assertFalse(any("/.venv/" in item or "/node_modules/" in item or "/.git/" in item for item in names))

            evidence = json.loads((result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(encoding="utf-8"))
            self.assertEqual(evidence["environment"]["scaffolder"]["id"], provider_id)
            self.assertEqual(evidence["environment"]["runtime"]["id"], "python")
            gates = {item["id"]: item["status"] for item in evidence["gates"]}
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(gates["unit-tests"], "PASSED")
            self.assertEqual(gates["pytest-tests"], "PASSED")
            self.assertEqual(claims["pytest-pass"], "VERIFIED")

            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["status"], "VERIFIED")
            self.assertEqual(restored["profile"], expected_profile)

    def test_python_mcp_server_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "python-mcp-server"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            package = project_name.replace("-", "_")
            self.assertTrue((result.project_root / "src" / package / "server.py").is_file())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            self.assertEqual(evidence["status"], "PARTIALLY_VERIFIED")
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["in-memory-tools"], "VERIFIED")
            self.assertEqual(claims["live-host"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)
            self.assertEqual(restored["status"], "PARTIALLY_VERIFIED")

    def test_wxt_extension_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "browser-extension-wxt"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            self.assertTrue((result.project_root / "wxt.config.ts").is_file())
            self.assertTrue((result.project_root / "entrypoints" / "background.ts").is_file())
            self.assertFalse((result.project_root / "manifest.json").exists())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            self.assertEqual(evidence["status"], "PARTIALLY_VERIFIED")
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["extension-zipped"], "VERIFIED")
            self.assertEqual(claims["chrome-runtime"], "UNVERIFIED")
            self.assertEqual(claims["firefox-runtime"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)
            self.assertEqual(restored["status"], "PARTIALLY_VERIFIED")

    def test_fastapi_service_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "python-http-service"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            package = project_name.replace("-", "_")
            self.assertTrue((result.project_root / "src" / package / "main.py").is_file())
            self.assertTrue((result.project_root / "src" / package / "routers" / "health.py").is_file())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            self.assertEqual(evidence["status"], "PARTIALLY_VERIFIED")
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["health-endpoint"], "VERIFIED")
            self.assertEqual(claims["live-http"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)
            self.assertEqual(restored["status"], "PARTIALLY_VERIFIED")

    def test_notebook_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "python-notebook"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            self.assertTrue((result.project_root / "notebooks" / "experiment.ipynb").is_file())
            self.assertTrue((result.project_root / "params.json").is_file())
            self.assertTrue((result.project_root / "data" / "SOURCES.md").is_file())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            self.assertEqual(evidence["status"], "PARTIALLY_VERIFIED")
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["notebook-executes"], "VERIFIED")
            self.assertEqual(claims["parameters-preserved"], "VERIFIED")
            self.assertEqual(claims["data-provenance-preserved"], "VERIFIED")
            self.assertEqual(claims["jupyter-lab-runtime"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)
            self.assertEqual(restored["status"], "PARTIALLY_VERIFIED")

    def test_rust_library_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "rust-library"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            self.assertTrue((result.project_root / "Cargo.toml").is_file())
            self.assertTrue((result.project_root / "src" / "lib.rs").is_file())
            self.assertFalse((result.project_root / "target").exists())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            self.assertEqual(evidence["status"], "PARTIALLY_VERIFIED")
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["crate-tests-pass"], "VERIFIED")
            self.assertEqual(claims["crate-builds"], "VERIFIED")
            self.assertEqual(claims["crates-io-publish"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)
            self.assertEqual(restored["status"], "PARTIALLY_VERIFIED")

    def test_wpf_desktop_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "csharp-desktop"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            self.assertTrue((result.project_root / "MainWindow.xaml").is_file())
            self.assertTrue((result.project_root / "ScaffoldStatus.cs").is_file())
            self.assertFalse((result.project_root / "bin").exists())
            self.assertFalse((result.project_root / "obj").exists())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            self.assertEqual(evidence["status"], "PARTIALLY_VERIFIED")
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["wpf-builds"], "VERIFIED")
            self.assertEqual(claims["window-shown"], "UNVERIFIED")
            self.assertEqual(claims["cross-platform-desktop"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)
            self.assertEqual(restored["status"], "PARTIALLY_VERIFIED")

    def test_avalonia_desktop_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "csharp-desktop-avalonia"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            self.assertTrue((result.project_root / "MainWindow.axaml").is_file())
            self.assertTrue((result.project_root / "App.axaml").is_file())
            self.assertTrue((result.project_root / "ScaffoldStatus.cs").is_file())
            self.assertFalse((result.project_root / "bin").exists())
            self.assertFalse((result.project_root / "obj").exists())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            self.assertEqual(evidence["status"], "PARTIALLY_VERIFIED")
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["avalonia-builds"], "VERIFIED")
            self.assertEqual(claims["window-shown"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)
            self.assertEqual(restored["status"], "PARTIALLY_VERIFIED")

    def test_vite_web_ui_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "typescript-web-ui"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            self.assertTrue((result.project_root / "vite.config.ts").is_file())
            self.assertTrue((result.project_root / "src" / "main.ts").is_file())
            self.assertFalse((result.project_root / "node_modules").exists())
            self.assertFalse((result.project_root / "dist").exists())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["frontend-builds"], "VERIFIED")
            self.assertIn(claims["browser-runtime"], {"VERIFIED", "UNVERIFIED"})
            if claims["browser-runtime"] == "VERIFIED":
                self.assertEqual(evidence["status"], "VERIFIED")
            else:
                self.assertEqual(evidence["status"], "PARTIALLY_VERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)
            self.assertEqual(restored["status"], evidence["status"])

    def test_vite_react_body_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "typescript-web-react"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            self.assertTrue((result.project_root / "src" / "App.tsx").is_file())
            self.assertTrue((result.project_root / "src" / "main.tsx").is_file())
            pkg = json.loads((result.project_root / "package.json").read_text(encoding="utf-8"))
            self.assertEqual(pkg["dependencies"]["react"], "18.3.1")
            self.assertEqual(pkg["devDependencies"]["vite"], "6.3.5")
            self.assertFalse((result.project_root / "node_modules").exists())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["frontend-builds"], "VERIFIED")
            self.assertIn(claims["browser-runtime"], {"VERIFIED", "UNVERIFIED"})
            if claims["browser-runtime"] == "VERIFIED":
                self.assertEqual(evidence["status"], "VERIFIED")
            else:
                self.assertEqual(evidence["status"], "PARTIALLY_VERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)
            self.assertEqual(restored["status"], evidence["status"])

    def test_typer_cli_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "python-cli-typer"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            package = project_name.replace("-", "_")
            self.assertTrue((result.project_root / "src" / package / "cli.py").is_file())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            self.assertEqual(evidence["status"], "VERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)
            self.assertEqual(restored["status"], "VERIFIED")

    def test_next_ssr_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "typescript-web-ssr"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            self.assertTrue((result.project_root / "app" / "page.tsx").is_file())
            pkg = json.loads((result.project_root / "package.json").read_text(encoding="utf-8"))
            self.assertEqual(pkg["dependencies"]["next"], "15.2.4")
            self.assertEqual(pkg["dependencies"]["react"], "18.3.1")
            self.assertFalse((result.project_root / ".next").exists())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            self.assertEqual(evidence["status"], "PARTIALLY_VERIFIED")
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["frontend-builds"], "VERIFIED")
            self.assertEqual(claims["server-runtime"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)
            self.assertEqual(restored["status"], "PARTIALLY_VERIFIED")

    @unittest.skipIf(shutil.which("maturin") is None, "maturin toolchain is required to build a Python native extension")
    def test_maturin_extension_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "python-native-extension"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            self.assertTrue((result.project_root / "src" / "lib.rs").is_file())
            self.assertTrue((result.project_root / "Cargo.toml").is_file())
            self.assertFalse((result.project_root / "target").exists())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            self.assertEqual(evidence["status"], "PARTIALLY_VERIFIED")
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["wheel-builds"], "VERIFIED")
            self.assertEqual(claims["python-import"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)
            self.assertEqual(restored["status"], "PARTIALLY_VERIFIED")

    def test_typescript_library_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "typescript-library"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            self.assertTrue((result.project_root / "src" / "index.ts").is_file())
            self.assertFalse((result.project_root / "node_modules").exists())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            self.assertEqual(evidence["status"], "VERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)
            self.assertEqual(restored["status"], "VERIFIED")

    def test_vue_web_body_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "typescript-web-vue"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            self.assertTrue((result.project_root / "src" / "App.vue").is_file())
            pkg = json.loads((result.project_root / "package.json").read_text(encoding="utf-8"))
            self.assertEqual(pkg["dependencies"]["vue"], "3.5.13")
            self.assertEqual(pkg["devDependencies"]["vite"], "6.3.5")
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["frontend-builds"], "VERIFIED")
            self.assertIn(claims["browser-runtime"], {"VERIFIED", "UNVERIFIED"})
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)
            self.assertEqual(restored["status"], evidence["status"])

    def test_aspnet_service_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "csharp-http-service"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            self.assertTrue((result.project_root / "Program.cs").is_file())
            self.assertTrue((result.project_root / "tests" / "HealthTests.cs").is_file())
            self.assertFalse((result.project_root / "bin").exists())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            self.assertEqual(evidence["status"], "PARTIALLY_VERIFIED")
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["health-endpoint"], "VERIFIED")
            self.assertEqual(claims["live-http"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)
            self.assertEqual(restored["status"], "PARTIALLY_VERIFIED")

    def test_vscode_extension_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "vscode-extension"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            self.assertTrue((result.project_root / "src" / "extension.ts").is_file())
            self.assertFalse((result.project_root / "node_modules").exists())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            self.assertEqual(evidence["status"], "PARTIALLY_VERIFIED")
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["vsix-builds"], "VERIFIED")
            self.assertEqual(claims["vscode-runtime"], "UNVERIFIED")
            self.assertEqual(claims["marketplace-publish"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)
            self.assertEqual(restored["status"], "PARTIALLY_VERIFIED")

    def test_github_action_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "github-action"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            self.assertTrue((result.project_root / "action.yml").is_file())
            self.assertTrue((result.project_root / "src" / "index.ts").is_file())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            self.assertEqual(evidence["status"], "PARTIALLY_VERIFIED")
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["action-builds"], "VERIFIED")
            self.assertEqual(claims["github-runtime"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)
            self.assertEqual(restored["status"], "PARTIALLY_VERIFIED")

    def test_docs_site_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "python-docs-site"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            self.assertTrue((result.project_root / "mkdocs.yml").is_file())
            self.assertTrue((result.project_root / "docs" / "index.md").is_file())
            self.assertFalse((result.project_root / "site").exists())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            self.assertEqual(evidence["status"], "PARTIALLY_VERIFIED")
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["docs-build"], "VERIFIED")
            self.assertEqual(claims["docs-serve"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)
            self.assertEqual(restored["status"], "PARTIALLY_VERIFIED")

    def test_astro_static_site_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "typescript-static-astro"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            self.assertTrue((result.project_root / "astro.config.mjs").is_file())
            self.assertTrue((result.project_root / "src" / "pages" / "index.astro").is_file())
            self.assertFalse((result.project_root / "node_modules").exists())
            self.assertFalse((result.project_root / "dist").exists())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            self.assertEqual(evidence["status"], "PARTIALLY_VERIFIED")
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["site-builds"], "VERIFIED")
            self.assertEqual(claims["site-preview"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)
            self.assertEqual(restored["status"], "PARTIALLY_VERIFIED")

    def test_svelte_body_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "typescript-web-svelte"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            self.assertTrue((result.project_root / "src" / "App.svelte").is_file())
            pkg = json.loads((result.project_root / "package.json").read_text(encoding="utf-8"))
            self.assertEqual(pkg["dependencies"]["svelte"], "5.16.0")
            self.assertFalse((result.project_root / "node_modules").exists())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["frontend-builds"], "VERIFIED")
            self.assertIn(claims["browser-runtime"], {"VERIFIED", "UNVERIFIED"})
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)

    def test_rust_cli_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "rust-cli"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            self.assertTrue((result.project_root / "src" / "lib.rs").is_file())
            self.assertTrue((result.project_root / "src" / "main.rs").is_file())
            self.assertFalse((result.project_root / "target").exists())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            self.assertEqual(evidence["status"], "PARTIALLY_VERIFIED")
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["crate-tests-pass"], "VERIFIED")
            self.assertEqual(claims["crate-builds"], "VERIFIED")
            self.assertEqual(claims["crates-io-publish"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)
            self.assertEqual(restored["status"], "PARTIALLY_VERIFIED")

    def test_axum_service_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "rust-http-service"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            self.assertTrue((result.project_root / "src" / "lib.rs").is_file())
            self.assertFalse((result.project_root / "target").exists())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            self.assertEqual(evidence["status"], "PARTIALLY_VERIFIED")
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["health-endpoint"], "VERIFIED")
            self.assertEqual(claims["live-http"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)
            self.assertEqual(restored["status"], "PARTIALLY_VERIFIED")

    def test_textual_tui_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "python-tui"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            package = project_name.replace("-", "_")
            self.assertTrue((result.project_root / "src" / package / "app.py").is_file())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            self.assertEqual(evidence["status"], "PARTIALLY_VERIFIED")
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["compose-status"], "VERIFIED")
            self.assertEqual(claims["tui-runtime"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)
            self.assertEqual(restored["status"], "PARTIALLY_VERIFIED")

    def test_lambda_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "python-lambda"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            package = project_name.replace("-", "_")
            self.assertTrue((result.project_root / "src" / package / "handler.py").is_file())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            self.assertEqual(evidence["status"], "PARTIALLY_VERIFIED")
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["handler-ok"], "VERIFIED")
            self.assertEqual(claims["aws-runtime"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)
            self.assertEqual(restored["status"], "PARTIALLY_VERIFIED")

    def test_cloudflare_worker_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "cloudflare-worker"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            self.assertTrue((result.project_root / "wrangler.toml").is_file())
            self.assertTrue((result.project_root / "src" / "index.js").is_file())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            self.assertEqual(evidence["status"], "PARTIALLY_VERIFIED")
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["tests-pass"], "VERIFIED")
            self.assertEqual(claims["cloudflare-runtime"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)
            self.assertEqual(restored["status"], "PARTIALLY_VERIFIED")

    def test_playwright_suite_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "playwright-test-suite"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            self.assertTrue((result.project_root / "playwright.config.ts").is_file())
            self.assertTrue((result.project_root / "fixtures" / "index.html").is_file())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["tests-pass"], "VERIFIED")
            self.assertIn(claims["browser-runtime"], {"VERIFIED", "UNVERIFIED"})
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)

    def test_commander_cli_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "typescript-cli"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            self.assertTrue((result.project_root / "src" / "cli.ts").is_file())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            self.assertEqual(evidence["status"], "PARTIALLY_VERIFIED")
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["cli-builds"], "VERIFIED")
            self.assertEqual(claims["npm-publish"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)

    def test_typescript_mcp_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "typescript-mcp-server"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            self.assertTrue((result.project_root / "src" / "server.ts").is_file())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            self.assertEqual(evidence["status"], "PARTIALLY_VERIFIED")
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["tests-pass"], "VERIFIED")
            self.assertEqual(claims["live-host"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)

    def test_data_pipeline_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "python-data-pipeline"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            package = project_name.replace("-", "_")
            self.assertTrue((result.project_root / "src" / package / "pipeline.py").is_file())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            self.assertEqual(evidence["status"], "PARTIALLY_VERIFIED")
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["transform-ok"], "VERIFIED")
            self.assertEqual(claims["scheduler-runtime"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)

    def test_alembic_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "python-schema-migration"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            self.assertTrue((result.project_root / "alembic.ini").is_file())
            self.assertTrue((result.project_root / "migrations" / "versions" / "0001_scaffold.py").is_file())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            self.assertEqual(evidence["status"], "PARTIALLY_VERIFIED")
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["sqlite-upgrade"], "VERIFIED")
            self.assertEqual(claims["postgres-migrate"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)

    def test_openapi_sdk_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "typescript-generated-sdk"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            self.assertTrue((result.project_root / "openapi.yaml").is_file())
            self.assertTrue((result.project_root / "src" / "client.ts").is_file())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            self.assertEqual(evidence["status"], "PARTIALLY_VERIFIED")
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["sdk-builds"], "VERIFIED")
            self.assertEqual(claims["live-api"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)

    def test_eval_harness_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "python-eval-harness"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            package = project_name.replace("-", "_")
            self.assertTrue((result.project_root / "src" / package / "harness.py").is_file())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["fixture-scores"], "VERIFIED")
            self.assertEqual(claims["model-runtime"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)

    def test_discord_bot_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "python-bot"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            package = project_name.replace("-", "_")
            self.assertTrue((result.project_root / "src" / package / "bot.py").is_file())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["command-registered"], "VERIFIED")
            self.assertEqual(claims["gateway-runtime"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)

    def test_scraper_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "python-scraper"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            self.assertTrue((result.project_root / "fixtures" / "page.html").is_file())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["fixture-parse"], "VERIFIED")
            self.assertEqual(claims["live-fetch"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)

    def test_hono_service_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "typescript-http-hono"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            self.assertTrue((result.project_root / "src" / "app.ts").is_file())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["tests-pass"], "VERIFIED")
            self.assertEqual(claims["live-http"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)

    def test_graphql_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "typescript-graphql"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            self.assertTrue((result.project_root / "src" / "schema.ts").is_file())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["tests-pass"], "VERIFIED")
            self.assertEqual(claims["live-http"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)

    def test_realtime_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "python-realtime"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            package = project_name.replace("-", "_")
            self.assertTrue((result.project_root / "src" / package / "app.py").is_file())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["websocket-status"], "VERIFIED")
            self.assertEqual(claims["live-http"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)

    def test_schema_contract_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "python-schema-contract"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            self.assertTrue((result.project_root / "openapi.yaml").is_file())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["spec-loads"], "VERIFIED")
            self.assertEqual(claims["live-spec"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)

    def test_agent_workflow_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "python-agent-workflow"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            package = project_name.replace("-", "_")
            self.assertTrue((result.project_root / "src" / package / "workflow.py").is_file())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["step-runs"], "VERIFIED")
            self.assertEqual(claims["llm-runtime"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)

    def test_design_system_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "typescript-design-system"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            self.assertTrue((result.project_root / "src" / "tokens.ts").is_file())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["tokens-build"], "VERIFIED")
            self.assertEqual(claims["visual-review"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)

    def test_experiment_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "python-experiment"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            self.assertTrue((result.project_root / "params.json").is_file())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["run-reproducible"], "VERIFIED")
            self.assertEqual(claims["training-runtime"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)

    def test_nest_service_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "typescript-http-nest"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            self.assertTrue((result.project_root / "src" / "health.controller.ts").is_file())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["tests-pass"], "VERIFIED")
            self.assertEqual(claims["live-http"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)

    def test_dbt_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "python-analytics-dbt"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            self.assertTrue((result.project_root / "dbt_project.yml").is_file())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertIn(claims["dbt-parses"], {"VERIFIED", "UNVERIFIED"})
            self.assertEqual(claims["warehouse-runtime"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)

    def test_rag_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "python-rag"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertTrue((result.project_root / "fixtures" / "docs.json").is_file())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["retrieve-ok"], "VERIFIED")
            self.assertEqual(claims["vector-runtime"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)

    def test_model_serving_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "python-model-serving"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            package = project_name.replace("-", "_")
            self.assertTrue((result.project_root / "src" / package / "serve.py").is_file())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["predict-ok"], "VERIFIED")
            self.assertEqual(claims["gpu-runtime"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)

    def test_compose_stack_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "python-container-stack"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertTrue((result.project_root / "compose.yaml").is_file())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["compose-loads"], "VERIFIED")
            self.assertEqual(claims["docker-runtime"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)

    def test_csharp_library_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "csharp-library"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertEqual(result.provider.provider_id, provider_id)
            self.assertTrue((result.project_root / "Text.cs").is_file())
            self.assertTrue((result.project_root / "tests" / "TextTests.cs").is_file())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["library-tests-pass"], "VERIFIED")
            self.assertEqual(claims["nuget-publish"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)

    def test_grpc_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "python-grpc"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            self.assertTrue((result.project_root / "status.proto").is_file())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["say-status"], "VERIFIED")
            self.assertEqual(claims["live-bind"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)

    def test_event_driven_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "python-event-driven"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            package = project_name.replace("-", "_")
            self.assertTrue((result.project_root / "src" / package / "worker.py").is_file())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["handle-ok"], "VERIFIED")
            self.assertEqual(claims["broker-runtime"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)

    def test_observability_generate_verify_and_restore_smoke(self) -> None:
        expected_profile = "python-observability"
        project_name, requirement, provider_id = CASES[expected_profile]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            result = generate_project(requirement, project_name, output)
            self.assertEqual(result.profile.profile_id, expected_profile)
            package = project_name.replace("-", "_")
            self.assertTrue((result.project_root / "src" / package / "probe.py").is_file())
            evidence = json.loads(
                (result.project_root / ".project" / "evidence" / "generation-verification.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(evidence["required_gates_passed"])
            claims = {item["id"]: item["status"] for item in evidence["claims"]}
            self.assertEqual(claims["span-recorded"], "VERIFIED")
            self.assertEqual(claims["collector-runtime"], "UNVERIFIED")
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["profile"], expected_profile)

    def test_secret_is_not_persisted_in_generated_project(self) -> None:
        secret = "sk-REDACTED_TEST_FIXTURE"
        requirement = f"做一个 Python 命令行工具。API_KEY={secret}，不要覆盖原始文件。"
        with tempfile.TemporaryDirectory() as temp_dir:
            result = generate_project(requirement, "redacted-cli", Path(temp_dir))
            for path in result.project_root.rglob("*"):
                if not path.is_file() or path.suffix in {".pyc", ".whl", ".gz"}:
                    continue
                try:
                    text = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
                self.assertNotIn(secret, text, path)

    def test_generator_refuses_to_overwrite_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            generate_project(CASES["python-cli"][1], "once-only-cli", output)
            with self.assertRaisesRegex(FactoryError, "Refusing to overwrite"):
                generate_project(CASES["python-cli"][1], "once-only-cli", output)

    def test_unresolved_requirement_does_not_materialize(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(FactoryError, "not usable"):
                generate_project("做一个手机应用。", "mobile-app", Path(temp_dir))
            self.assertFalse(any(Path(temp_dir).iterdir()))

    def test_generator_blocks_when_formula_requires_unimplemented_strict_verification(self) -> None:
        requirement = "做一个 Python 命令行工具，可靠性要求极高。"
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            with self.assertRaisesRegex(FactoryError, "cannot be honestly materialized"):
                generate_project(requirement, "strict-cli", output)
            self.assertFalse(any(output.iterdir()))

    def test_generator_blocks_non_bootstrap_intent_before_materialization(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            with self.assertRaisesRegex(FactoryError, "not a new-project bootstrap"):
                generate_project(
                    CASES["python-cli"][1],
                    "not-a-bootstrap",
                    output,
                    intent=IntentSnapshot(kind="refactor", change_scope="local", risk="normal"),
                    repository=RepositoryState(existing_project=True, clean_worktree=True),
                )
            self.assertFalse(any(output.iterdir()))

    def test_generator_blocks_materialization_depth_it_cannot_honor(self) -> None:
        requirement = "做一个大型 Python 命令行工具。"
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            with self.assertRaisesRegex(FactoryError, "materialization"):
                generate_project(requirement, "large-cli", output)
            self.assertFalse(any(output.iterdir()))


class P6HarnessProcessIntegrationTests(unittest.TestCase):
    def test_default_generation_materializes_identical_codex_and_claude_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = generate_project(CASES["python-cli"][1], "dual-harness-cli", Path(temp_dir))
            canonical = (result.project_root / ".project/contract/agent-contract.md").read_bytes()
            self.assertEqual((result.project_root / "AGENTS.md").read_bytes(), canonical)
            self.assertEqual((result.project_root / "CLAUDE.md").read_bytes(), canonical)
            self.assertEqual(result.harness_compatibility["status"], "PARTIALLY_VERIFIED")
            lock = json.loads((result.project_root / "project.lock.json").read_text(encoding="utf-8"))
            self.assertEqual(lock["lock_schema_version"], "0.9")
            self.assertEqual(lock["compatibility_policy"]["provider_generation_requires"], "SUPPORTED")
            self.assertFalse(lock["compatibility_policy"]["automatic_promotion"])
            self.assertTrue(all(item["compatibility_state"] == "SUPPORTED" for item in lock["providers"].values()))
            self.assertEqual(set(lock["harness_contract"]["adapters"]), {"codex", "claude"})
            self.assertFalse(lock["harness_contract"]["runtime_verified"])
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["harness_compatibility"]["status"], "PARTIALLY_VERIFIED")

    def test_single_harness_does_not_materialize_other_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = generate_project(
                CASES["python-cli"][1],
                "codex-only-cli",
                Path(temp_dir),
                harnesses=("codex",),
            )
            self.assertTrue((result.project_root / "AGENTS.md").is_file())
            self.assertFalse((result.project_root / "CLAUDE.md").exists())
            lock = json.loads((result.project_root / "project.lock.json").read_text(encoding="utf-8"))
            self.assertEqual(set(lock["harness_contract"]["adapters"]), {"codex"})

    def test_spec_kit_plan_is_optional_and_never_claims_runtime_installation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = generate_project(
                CASES["python-cli"][1],
                "planned-process-cli",
                Path(temp_dir),
                process_integration="spec-kit",
                process_mode="plan",
            )
            self.assertIsNotNone(result.process_integration)
            assert result.process_integration is not None
            self.assertEqual(result.process_integration["status"], "PLANNED_NOT_INSTALLED")
            self.assertFalse((result.project_root / ".specify").exists())
            self.assertTrue((result.project_root / ".project/process/spec-kit-plan.json").is_file())
            lock = json.loads((result.project_root / "project.lock.json").read_text(encoding="utf-8"))
            self.assertEqual(lock["process_integration"]["provider"]["id"], "spec-kit")
            self.assertEqual(lock["process_integration"]["provider"]["upstream_version"], "1.0.1")
            self.assertEqual(lock["process_integration"]["status"], "PLANNED_NOT_INSTALLED")
            self.assertFalse(lock["process_integration"]["runtime_verified"])
            restored = restore_verify_project_zip(result.project_zip)
            self.assertEqual(restored["process_integration"]["status"], "PLANNED_NOT_INSTALLED")

    def test_unknown_harness_blocks_before_final_materialization(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            with self.assertRaisesRegex(FactoryError, "Unknown harness adapter"):
                generate_project(
                    CASES["python-cli"][1],
                    "unknown-harness",
                    output,
                    harnesses=("not-real",),
                )
            self.assertFalse(any(output.iterdir()))

    def test_process_execute_without_provider_blocks_before_final_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            with self.assertRaisesRegex(FactoryError, "not available"):
                generate_project(
                    CASES["python-cli"][1],
                    "missing-specify",
                    output,
                    process_integration="spec-kit",
                    process_mode="execute",
                    process_env={"PATH": ""},
                )
            self.assertFalse(any(output.iterdir()))
