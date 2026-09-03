from __future__ import annotations

import json
import yaml
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from project_factory.normalizer import normalize_requirement  # noqa: E402


class ArchitectureGuardTests(unittest.TestCase):
    def test_provider_and_harness_vocabulary_is_not_a_blueprint_root_surface(self):
        schema = json.loads((ROOT / "schemas" / "blueprint.schema.json").read_text(encoding="utf-8"))
        props = set(schema["properties"])
        forbidden = {
            "provider",
            "providers",
            "runner",
            "harness",
            "agent",
            "agents",
            "spec_kit",
            "copier",
            "dagu",
            "aionui",
            "codex",
            "claude",
        }
        self.assertTrue(props.isdisjoint(forbidden))

    def test_normalizer_does_not_create_components_from_language_mentions(self):
        result = normalize_requirement("大型系统，TypeScript 前端、Python 后端、Rust 核心库。")
        self.assertNotIn("components", result.blueprint)

    def test_normalizer_does_not_add_quality_attributes_from_project_seriousness(self):
        result = normalize_requirement("做一个大型长期 Python 服务。")
        self.assertNotIn("constraints", result.blueprint)

    def test_normalizer_does_not_add_runner_for_long_lived_project(self):
        result = normalize_requirement("做一个长期维护的大型 Python 命令行工具。")
        serialized = json.dumps(result.blueprint, ensure_ascii=False).casefold()
        for word in ("runner", "dagu", "heartbeat", "retry", "timeout"):
            self.assertNotIn(word, serialized)

    def test_factory_core_does_not_embed_profile_recipe_ids(self):
        text = (ROOT / "src" / "project_factory" / "factory.py").read_text(encoding="utf-8")
        forbidden_recipe_ids = {
            "uv-app",
            "uv-lib",
            "uv-mcp-server",
            "uv-fastapi-service",
            "uv-notebook",
            "uv-typer-app",
            "cargo-lib",
            "dotnet-wpf",
            "dotnet-avalonia",
            "npm-library",
            "npm-browser-extension",
            "npm-wxt-extension",
            "npm-vite-web",
            "npm-vite-react",
            "npm-vite-vue",
            "npm-ts-library",
            "npm-next-web",
            "dotnet-aspnet",
            "npm-vscode-extension",
            "npm-github-action",
            "uv-mkdocs",
            "npm-astro",
            "npm-vite-svelte",
            "cargo-cli",
            "cargo-axum",
            "uv-textual-tui",
            "uv-lambda",
            "npm-cloudflare-worker",
            "npm-playwright-suite",
            "npm-commander-cli",
            "npm-mcp-server",
            "uv-data-pipeline",
            "uv-alembic",
            "npm-openapi-sdk",
            "uv-eval-harness",
            "uv-discord-bot",
            "uv-scraper",
            "npm-hono",
            "npm-graphql",
            "uv-realtime",
            "uv-schema-contract",
            "uv-agent-workflow",
            "npm-design-system",
            "uv-experiment",
            "npm-nest",
            "uv-dbt",
            "uv-rag",
            "uv-model-serving",
            "uv-compose-stack",
            "dotnet-library",
            "uv-grpc",
            "uv-event-driven",
            "uv-observability",
            "maturin-pyo3",
            "python-cli",
            "python-cli-typer",
            "python-library",
            "python-mcp-server",
            "python-http-service",
            "python-notebook",
            "python-native-extension",
            "rust-library",
            "csharp-desktop",
            "csharp-desktop-avalonia",
            "typescript-web-ui",
            "typescript-web-react",
            "typescript-web-ssr",
            "typescript-web-vue",
            "typescript-library",
            "csharp-http-service",
            "vscode-extension",
            "github-action",
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
            "node-library",
            "browser-extension-js",
            "browser-extension-wxt",
        }
        for recipe_id in forbidden_recipe_ids:
            self.assertNotIn(f'"{recipe_id}"', text)

    def test_normalizer_keeps_raw_request_as_explicit_purpose(self):
        text = "做一个 Python 命令行工具，不要替我决定云平台。"
        result = normalize_requirement(text)
        self.assertEqual(result.blueprint["project"]["purpose"], text)
        self.assertEqual(result.metadata["provenance"]["/project/purpose"]["source"], "EXPLICIT")


if __name__ == "__main__":
    unittest.main()


class P4VerificationArchitectureGuardTests(unittest.TestCase):
    def test_scaffold_recipes_do_not_own_verification_spine(self) -> None:
        from pathlib import Path
        import project_factory.recipes as recipes
        source = Path(recipes.__file__).read_text(encoding="utf-8")
        forbidden = [
            "def run_verification(",
            "def verification_environment(",
            "def verification_limitations(",
            "def display_verification_commands(",
        ]
        for marker in forbidden:
            self.assertNotIn(marker, source)

    def test_factory_core_does_not_embed_verification_gate_ids(self) -> None:
        from pathlib import Path
        import project_factory.factory as factory
        source = Path(factory.__file__).read_text(encoding="utf-8")
        for marker in ["cli-runs", "unit-tests", "manifest-check", "chrome-runtime", "firefox-runtime"]:
            self.assertNotIn(marker, source)


class P5DecisionArchitectureGuardTests(unittest.TestCase):
    def test_factory_core_uses_semantic_boundary_not_raw_normalizer(self) -> None:
        text = (ROOT / "src" / "project_factory" / "factory.py").read_text(encoding="utf-8")
        self.assertNotIn("normalize_requirement", text)
        self.assertIn("run_semantic_intake", text)

    def test_decision_core_does_not_embed_formula_adapter_implementation_ids(self) -> None:
        text = (ROOT / "src" / "project_factory" / "decision.py").read_text(encoding="utf-8")
        self.assertNotIn("baseline-engineering-v1", text)
        self.assertNotIn("subprocess", text)
        self.assertNotIn("os.system", text)

    def test_formula_and_policy_layers_do_not_execute_processes(self) -> None:
        for relative in ("src/project_factory/formulas.py", "src/project_factory/policies.py"):
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertNotIn("subprocess", text, relative)
            self.assertNotIn("os.system", text, relative)


class P6HarnessArchitectureGuardTests(unittest.TestCase):
    def test_factory_core_does_not_embed_harness_or_process_product_ids(self) -> None:
        text = (ROOT / "src" / "project_factory" / "factory.py").read_text(encoding="utf-8").casefold()
        for marker in ("codex", "claude", "spec-kit", "speckit", "agents.md", "claude.md"):
            self.assertNotIn(marker, text)

    def test_process_registry_contains_metadata_not_arbitrary_commands(self) -> None:
        import yaml
        data = yaml.safe_load((ROOT / "src/project_factory/registry_data/process_integrations.yaml").read_text(encoding="utf-8"))
        serialized = json.dumps(data, ensure_ascii=False).casefold()
        for key in ('"commands"', '"shell"', '"argv"'):
            self.assertNotIn(key, serialized)

    def test_harness_contract_implementation_is_outside_factory_core(self) -> None:
        factory_text = (ROOT / "src/project_factory/factory.py").read_text(encoding="utf-8")
        harness_text = (ROOT / "src/project_factory/harness.py").read_text(encoding="utf-8")
        self.assertNotIn("def render_agent_contract(", factory_text)
        self.assertIn("def render_agent_contract(", harness_text)

class P7CompatibilityArchitectureGuards(unittest.TestCase):
    def test_compatibility_core_does_not_become_network_crawler(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "src" / "project_factory" / "compatibility.py").read_text(encoding="utf-8")
        forbidden = ("requests.", "urllib.request", "httpx.", "aiohttp", "github.com/" )
        for marker in forbidden:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, text)

    def test_dynamic_observations_are_outside_registry_data(self) -> None:
        root = Path(__file__).resolve().parents[1]
        registry_text = (root / "src" / "project_factory" / "registry_data" / "compatibility.yaml").read_text(encoding="utf-8")
        self.assertNotIn("observed_latest", registry_text)
        self.assertNotIn("published_at", registry_text)

class P8UpgradeArchitectureGuards(unittest.TestCase):
    def test_upgrade_core_has_no_network_or_upstream_discovery(self) -> None:
        text = (ROOT / "src/project_factory/upgrade.py").read_text(encoding="utf-8")
        for marker in ("requests.", "urllib.request", "httpx.", "aiohttp", "github.com/"):
            self.assertNotIn(marker, text)

    def test_upgrade_targets_factory_overlay_not_source_trees(self) -> None:
        text = (ROOT / "src/project_factory/upgrade.py").read_text(encoding="utf-8")
        for marker in ('"src/"', '"tests/"'):
            self.assertNotIn(marker, text)
        self.assertIn("render_overlay_targets", text)

    def test_no_automatic_apply_flag_is_exposed(self) -> None:
        text = (ROOT / "src/project_factory/upgrade.py").read_text(encoding="utf-8")
        self.assertNotIn("--auto-apply", text)
        self.assertIn("--confirm-plan", text)


class P9ExtensionArchitectureGuards(unittest.TestCase):
    def test_extension_core_does_not_install_or_fetch_packages(self) -> None:
        text = (ROOT / "src/project_factory/extensions.py").read_text(encoding="utf-8").casefold()
        for marker in ("subprocess", "pip install", "uv tool install", "urllib.request", "requests.", "httpx.", "aiohttp"):
            self.assertNotIn(marker, text)

    def test_extension_remove_is_registration_only(self) -> None:
        text = (ROOT / "src/project_factory/extensions.py").read_text(encoding="utf-8")
        for marker in ("shutil.rmtree", ".unlink(", "os.remove("):
            self.assertNotIn(marker, text)
        self.assertIn('"package_or_source_deleted": False', text)

    def test_factory_core_does_not_embed_fixture_extension_ids(self) -> None:
        text = (ROOT / "src/project_factory/factory.py").read_text(encoding="utf-8")
        for marker in ("team-standard", "trusted-lab"):
            self.assertNotIn(marker, text)

    def test_extension_migrations_are_namespace_scoped(self) -> None:
        text = (ROOT / "src/project_factory/extensions.py").read_text(encoding="utf-8")
        self.assertIn('Path(".project") / "extensions" / extension_id', text)
        self.assertIn("attempted to modify outside its namespace", text)

class P10HostArchitectureGuards(unittest.TestCase):
    def test_factory_core_does_not_embed_host_product_id(self) -> None:
        source = (ROOT / "src/project_factory/factory.py").read_text(encoding="utf-8").casefold()
        self.assertNotIn("aionui", source)

    def test_host_core_does_not_install_launch_or_own_runner(self) -> None:
        source = (ROOT / "src/project_factory/host.py").read_text(encoding="utf-8").casefold()
        for forbidden in ("subprocess", "pip install", "uv tool install", "from .extensions", "from .verification", "from .process"):
            self.assertNotIn(forbidden, source)

    def test_host_registry_is_metadata_not_arbitrary_commands(self) -> None:
        data = yaml.safe_load((ROOT / "src/project_factory/registry_data/hosts.yaml").read_text(encoding="utf-8"))
        serialized = json.dumps(data, ensure_ascii=False).casefold()
        for forbidden in ("command:", "argv", "shell", "install_command", "launch_command"):
            self.assertNotIn(forbidden, serialized)

class P11RunnerArchitectureGuards(unittest.TestCase):
    def test_factory_core_does_not_embed_runner_provider_product_id(self) -> None:
        source = (ROOT / "src/project_factory/factory.py").read_text(encoding="utf-8").casefold()
        self.assertNotIn('"dagu"', source)

    def test_runner_core_does_not_install_fetch_or_launch_interactive_host(self) -> None:
        source = (ROOT / "src/project_factory/runner.py").read_text(encoding="utf-8").casefold()
        for forbidden in (
            "pip install",
            "uv tool install",
            "urllib.request",
            "requests.",
            "httpx.",
            "aiohttp",
            "from .host",
            "import project_factory.host",
            "type: controller",
        ):
            self.assertNotIn(forbidden, source)

    def test_runner_registry_does_not_claim_factory_ownership_domains(self) -> None:
        data = yaml.safe_load((ROOT / "src/project_factory/registry_data/runners.yaml").read_text(encoding="utf-8"))
        item = data["runners"][0]
        self.assertTrue(all(value is False for value in item["boundaries"].values()))
        self.assertEqual(item["upstream_contract"]["tag_commit"], "a1a3c286b26cbad934bb9f8344f2f9aa51385981")

    def test_runner_runtime_state_lock_is_not_factory_overlay_owned(self) -> None:
        source = (ROOT / "src/project_factory/ownership.py").read_text(encoding="utf-8")
        self.assertNotIn("ACTIVE_RUN.lock", source)


class P12ProductizationArchitectureGuards(unittest.TestCase):
    def test_product_doctor_does_not_install_or_fetch(self) -> None:
        source = (ROOT / "src/project_factory/product.py").read_text(encoding="utf-8").casefold()
        for marker in ("pip install", "uv tool install", "urllib.request", "requests.", "httpx.", "aiohttp"):
            self.assertNotIn(marker, source)

    def test_checkpoint_recovery_never_auto_deletes_or_overwrites(self) -> None:
        source = (ROOT / "src/project_factory/recovery.py").read_text(encoding="utf-8")
        for marker in ("shutil.rmtree", ".unlink(", "os.remove("):
            self.assertNotIn(marker, source)
        self.assertIn('open("xb")', source)
        self.assertIn("refusing to overwrite", source.casefold())

    def test_productization_is_not_gui_or_runner_or_package_manager(self) -> None:
        source = (ROOT / "src/project_factory/product.py").read_text(encoding="utf-8").casefold()
        for marker in ("tkinter", "pyqt", "electron", "pip._internal", "schedule.every", "start_runner("):
            self.assertNotIn(marker, source)


class StageEOverlayArchitectureGuards(unittest.TestCase):
    def test_factory_core_does_not_embed_overlay_engine_name(self) -> None:
        text = (ROOT / "src/project_factory/factory.py").read_text(encoding="utf-8").casefold()
        self.assertNotIn("copier", text)
        self.assertIn("apply_factory_overlay", text)

    def test_kernel_dependencies_stay_tiny(self) -> None:
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8").casefold()
        self.assertNotIn("copier", text)
        self.assertIn("jsonschema==4.26.0", text)
        self.assertIn("pyyaml==6.0.3", text)

    def test_packaged_overlay_template_excludes_language_roots(self) -> None:
        from project_factory.overlay import _load_copier_config, destination_is_forbidden

        config = _load_copier_config()
        exclude = {str(item) for item in config["_exclude"]}
        for item in ("src", "tests", "pyproject.toml", "package.json"):
            self.assertIn(item, exclude)
        for relative in ("src/app.py", "tests/test_x.py", "pyproject.toml", "package.json"):
            self.assertTrue(destination_is_forbidden(relative), relative)
