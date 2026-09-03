from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from project_factory.registry import (
    RegistryError,
    inspect_provider,
    load_registry,
    resolve_providers,
    select_profile,
)


class RegistryIntegrityTests(unittest.TestCase):
    def test_default_registry_cross_references_are_valid(self) -> None:
        registry = load_registry()
        self.assertEqual(set(registry.capabilities), {"project_scaffolding", "long_running_execution"})
        self.assertEqual(set(registry.providers), {"uv", "npm", "cargo", "dotnet"})
        self.assertEqual(
            set(registry.profiles),
            {
                "python-cli",
                "python-cli-typer",
                "python-library",
                "python-mcp-server",
                "node-library",
                "browser-extension-js",
                "browser-extension-wxt",
                "python-http-service",
                "python-notebook",
                "python-native-extension",
                "rust-library",
                "csharp-desktop",
                "csharp-desktop-avalonia",
                "typescript-web-ui",
                "typescript-web-react",
                "typescript-web-ssr",
                "typescript-library",
                "typescript-web-vue",
                "csharp-http-service",
                "vscode-extension",
                "github-action",
                "iac-opentofu",
                "python-docs-site",
                "typescript-static-astro",
                "typescript-web-svelte",
                "rust-cli",
                "rust-http-service",
                "python-tui",
                "python-lambda",
                "cloudflare-worker",
                "playwright-test-suite",
                "typescript-cli",
                "typescript-mcp-server",
                "python-data-pipeline",
                "python-schema-migration",
                "typescript-generated-sdk",
                "python-eval-harness",
                "python-bot",
                "python-scraper",
                "typescript-http-hono",
                "typescript-graphql",
                "python-realtime",
                "python-schema-contract",
                "python-agent-workflow",
                "typescript-design-system",
                "python-experiment",
                "typescript-http-nest",
                "python-analytics-dbt",
                "python-rag",
                "python-model-serving",
                "python-container-stack",
                "csharp-library",
                "python-grpc",
                "python-event-driven",
                "python-observability",
            },
        )
        self.assertEqual(set(registry.formulas), {"baseline-engineering"})
        self.assertEqual(set(registry.policies), {"safe-defaults"})

    def test_provider_registry_records_zero_upstream_modification(self) -> None:
        registry = load_registry()
        self.assertTrue(all(not item.upstream_source_modified for item in registry.providers.values()))

    def test_every_profile_declares_a_non_empty_family(self) -> None:
        # O1: family is the single source of truth for the selection advisor's
        # overlap grouping. A missing family would silently disable overlap warnings
        # for that car series, so it must be declared on every profile.
        registry = load_registry()
        missing = [pid for pid, spec in registry.profiles.items() if not spec.family]
        self.assertEqual(missing, [])
        # The two overlap-prone families must be exactly the web/service car series
        # the advisor highlights; everything else is its own family (no surprise warnings).
        web = {pid for pid, spec in registry.profiles.items() if spec.family == "web"}
        service = {pid for pid, spec in registry.profiles.items() if spec.family == "service"}
        self.assertEqual(
            web,
            {
                "typescript-web-ui", "typescript-web-react", "typescript-web-vue",
                "typescript-web-svelte", "typescript-web-ssr",
            },
        )
        self.assertEqual(
            service,
            {
                "python-http-service", "csharp-http-service", "rust-http-service",
                "typescript-http-nest", "typescript-http-hono",
            },
        )

    def test_actual_provider_versions_are_detected(self) -> None:
        # T23: the factory detects and reports the local version; it no longer
        # requires the version to be in tested_versions (developer freedom).
        registry = load_registry()
        for provider in registry.providers.values():
            with self.subTest(provider=provider.id):
                runtime = inspect_provider(provider)
                self.assertTrue(runtime.version)
                self.assertIn(runtime.version_status, ("SUPPORTED", "COMPATIBLE"))

    def test_unlisted_provider_version_is_reported_not_rejected(self) -> None:
        # T23: a version outside tested_versions is reported as COMPATIBLE, not raised.
        registry = load_registry()
        spec = registry.providers["uv"]
        completed = mock.Mock(returncode=0, stdout="uv 99.0.0\n", stderr="")
        with mock.patch("project_factory.tools.resolve_executable", return_value="/fake/uv"):
            with mock.patch("project_factory.registry.subprocess.run", return_value=completed):
                runtime = inspect_provider(spec)
        self.assertEqual(runtime.version, "99.0.0")
        self.assertEqual(runtime.version_status, "COMPATIBLE")

    def test_missing_executable_is_visible_block(self) -> None:
        spec = load_registry().providers["uv"]
        with mock.patch("project_factory.tools.resolve_executable", return_value=None):
            with self.assertRaisesRegex(RegistryError, "not found"):
                inspect_provider(spec)

    def test_ambiguous_equal_priority_profiles_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = Path(__file__).resolve().parents[1] / "src" / "project_factory" / "registry_data"
            for name in ("capabilities.yaml", "providers.yaml", "profiles.yaml", "formulas.yaml", "policies.yaml"):
                (root / name).write_text((source / name).read_text(encoding="utf-8"), encoding="utf-8")
            doc = yaml.safe_load((root / "profiles.yaml").read_text(encoding="utf-8"))
            clone = dict(next(item for item in doc["profiles"] if item["id"] == "python-cli"))
            clone["id"] = "python-cli-tie"
            doc["profiles"].append(clone)
            (root / "profiles.yaml").write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
            registry = load_registry(root)
            blueprint = {
                "schema_version": "0.1",
                "project": {"purpose": "CLI"},
                "work_products": [{"kind": "cli"}],
                "technology": {"required": ["python"]},
            }
            with self.assertRaisesRegex(RegistryError, "Ambiguous profile"):
                select_profile(blueprint, registry)


class ProfileResolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = load_registry()

    def profile_for(self, product: str, technology: str) -> str:
        blueprint = {
            "schema_version": "0.1",
            "project": {"purpose": "test"},
            "work_products": [{"kind": product}],
            "technology": {"required": [technology]},
        }
        return select_profile(blueprint, self.registry).id

    def test_four_families_resolve(self) -> None:
        self.assertEqual(self.profile_for("cli", "python"), "python-cli")
        self.assertEqual(self.profile_for("cli", "typer"), "python-cli-typer")
        self.assertEqual(self.profile_for("native-extension", "rust"), "python-native-extension")
        self.assertEqual(self.profile_for("library", "python"), "python-library")
        self.assertEqual(self.profile_for("library", "javascript"), "node-library")
        self.assertEqual(self.profile_for("browser-extension", "javascript"), "browser-extension-js")
        self.assertEqual(self.profile_for("browser-extension", "typescript"), "browser-extension-wxt")
        self.assertEqual(self.profile_for("mcp-server", "python"), "python-mcp-server")
        self.assertEqual(self.profile_for("service", "python"), "python-http-service")
        self.assertEqual(self.profile_for("http-service", "python"), "python-http-service")
        self.assertEqual(self.profile_for("notebook", "python"), "python-notebook")
        self.assertEqual(self.profile_for("library", "rust"), "rust-library")
        self.assertEqual(self.profile_for("desktop-app", "csharp"), "csharp-desktop")
        self.assertEqual(self.profile_for("desktop-app", "avalonia"), "csharp-desktop-avalonia")
        self.assertEqual(self.profile_for("web-ui", "typescript"), "typescript-web-ui")
        self.assertEqual(self.profile_for("web-spa", "typescript"), "typescript-web-ui")
        self.assertEqual(self.profile_for("web-ui", "react"), "typescript-web-react")
        self.assertEqual(self.profile_for("web-ssr", "nextjs"), "typescript-web-ssr")
        self.assertEqual(self.profile_for("web-ui", "nextjs"), "typescript-web-ssr")
        self.assertEqual(self.profile_for("library", "typescript"), "typescript-library")
        self.assertEqual(self.profile_for("web-spa", "vue"), "typescript-web-vue")
        self.assertEqual(self.profile_for("service", "csharp"), "csharp-http-service")
        self.assertEqual(self.profile_for("vscode-extension", "typescript"), "vscode-extension")
        self.assertEqual(self.profile_for("ci-action", "typescript"), "github-action")
        self.assertEqual(self.profile_for("docs-site", "python"), "python-docs-site")
        self.assertEqual(self.profile_for("static-site", "astro"), "typescript-static-astro")
        self.assertEqual(self.profile_for("web-spa", "svelte"), "typescript-web-svelte")
        self.assertEqual(self.profile_for("cli", "rust"), "rust-cli")
        self.assertEqual(self.profile_for("cli", "clap"), "rust-cli")
        self.assertEqual(self.profile_for("service", "rust"), "rust-http-service")
        self.assertEqual(self.profile_for("service", "axum"), "rust-http-service")
        self.assertEqual(self.profile_for("tui", "python"), "python-tui")
        self.assertEqual(self.profile_for("serverless-function", "python"), "python-lambda")
        self.assertEqual(self.profile_for("serverless-function", "lambda"), "python-lambda")
        self.assertEqual(self.profile_for("serverless-function", "cloudflare"), "cloudflare-worker")
        self.assertEqual(self.profile_for("test-suite", "playwright"), "playwright-test-suite")
        self.assertEqual(self.profile_for("cli", "commander"), "typescript-cli")
        self.assertEqual(self.profile_for("cli", "typescript"), "typescript-cli")
        self.assertEqual(self.profile_for("mcp-server", "typescript"), "typescript-mcp-server")
        self.assertEqual(self.profile_for("data-pipeline", "python"), "python-data-pipeline")
        self.assertEqual(self.profile_for("schema-migration-repo", "python"), "python-schema-migration")
        self.assertEqual(self.profile_for("generated-sdk", "typescript"), "typescript-generated-sdk")
        self.assertEqual(self.profile_for("eval-harness", "python"), "python-eval-harness")
        self.assertEqual(self.profile_for("bot", "python"), "python-bot")
        self.assertEqual(self.profile_for("scraper", "python"), "python-scraper")
        self.assertEqual(self.profile_for("service", "hono"), "typescript-http-hono")
        self.assertEqual(self.profile_for("service", "typescript"), "typescript-http-hono")
        self.assertEqual(self.profile_for("graphql-api", "typescript"), "typescript-graphql")
        self.assertEqual(self.profile_for("realtime-service", "python"), "python-realtime")
        self.assertEqual(self.profile_for("schema-contract", "python"), "python-schema-contract")
        self.assertEqual(self.profile_for("agent-workflow", "python"), "python-agent-workflow")
        self.assertEqual(self.profile_for("design-system", "typescript"), "typescript-design-system")
        self.assertEqual(self.profile_for("experiment", "python"), "python-experiment")
        self.assertEqual(self.profile_for("service", "nestjs"), "typescript-http-nest")
        self.assertEqual(self.profile_for("analytics-transform", "python"), "python-analytics-dbt")
        self.assertEqual(self.profile_for("rag-application", "python"), "python-rag")
        self.assertEqual(self.profile_for("model-serving", "python"), "python-model-serving")
        self.assertEqual(self.profile_for("container-stack", "python"), "python-container-stack")
        self.assertEqual(self.profile_for("library", "csharp"), "csharp-library")
        self.assertEqual(self.profile_for("grpc-service", "python"), "python-grpc")
        self.assertEqual(self.profile_for("event-driven-app", "python"), "python-event-driven")
        self.assertEqual(self.profile_for("observability-agent", "python"), "python-observability")

    def test_javascript_browser_extension_keeps_handwritten_mv3_line(self) -> None:
        self.assertEqual(self.profile_for("browser-extension", "javascript"), "browser-extension-js")

    def test_provider_preferences_resolve_by_capability(self) -> None:
        profile = self.registry.profiles["node-library"]
        resolved = resolve_providers(profile, self.registry)
        self.assertEqual(resolved["project_scaffolding"].spec.id, "npm")
