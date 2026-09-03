from __future__ import annotations

import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from project_factory.verification import (
    ClaimSpec,
    GateSpec,
    VerificationError,
    VerificationSuite,
    assert_required_gates,
    build_verification_suite,
    execute_verification_suite,
)


@dataclass(frozen=True)
class FakeProvider:
    provider_id: str = "test-provider"
    provider_version: str = "1.0"
    executable: str = sys.executable


class VerificationSpineTests(unittest.TestCase):
    def test_verified_claim_requires_passing_evidence_gate(self) -> None:
        suite = VerificationSuite(
            id="unit",
            version="0.1",
            scope="unit",
            gates=(GateSpec("g1", "probe", "command", (sys.executable, "-c", "print('ok')"), ("ok",)),),
            claims=(ClaimSpec("c1", "Probe works", "unit", ("g1",)),),
            runtime_kind="none",
        )
        with tempfile.TemporaryDirectory() as tmp:
            report = execute_verification_suite(suite, Path(tmp), FakeProvider())
        self.assertEqual(report["status"], "VERIFIED")
        self.assertEqual(report["claims"][0]["status"], "VERIFIED")
        self.assertEqual(report["gates"][0]["evidence_level"], "PASSED")

    def test_command_failure_is_recorded_and_blocks_required_gate(self) -> None:
        suite = VerificationSuite(
            id="failure",
            version="0.1",
            scope="unit",
            gates=(GateSpec("g1", "failing probe", "command", (sys.executable, "-c", "raise SystemExit(7)")),),
            claims=(ClaimSpec("c1", "Probe works", "unit", ("g1",)),),
            runtime_kind="none",
        )
        with tempfile.TemporaryDirectory() as tmp:
            report = execute_verification_suite(suite, Path(tmp), FakeProvider())
        self.assertEqual(report["status"], "FAILED")
        self.assertEqual(report["gates"][0]["status"], "FAILED")
        self.assertEqual(report["gates"][0]["evidence_level"], "EXECUTED")
        with self.assertRaises(VerificationError):
            assert_required_gates(report)

    def test_unverified_material_claim_makes_report_partial_without_faking_failure(self) -> None:
        suite = VerificationSuite(
            id="partial",
            version="0.1",
            scope="unit",
            gates=(GateSpec("g1", "probe", "command", (sys.executable, "-c", "print('ok')"), ("ok",)),),
            claims=(
                ClaimSpec("verified", "Local probe works", "local", ("g1",)),
                ClaimSpec("external", "External runtime works", "external", (), True, "External runtime was not launched."),
            ),
            runtime_kind="none",
        )
        with tempfile.TemporaryDirectory() as tmp:
            report = execute_verification_suite(suite, Path(tmp), FakeProvider())
        self.assertTrue(report["required_gates_passed"])
        self.assertEqual(report["status"], "PARTIALLY_VERIFIED")
        self.assertEqual(report["claims"][1]["status"], "UNVERIFIED")
        assert_required_gates(report)

    def test_artifact_gate_hashes_actual_file(self) -> None:
        suite = VerificationSuite(
            id="artifact",
            version="0.1",
            scope="unit",
            gates=(GateSpec("artifact", "artifact", "artifact", artifact_patterns=("dist/*.whl",), min_artifacts=1),),
            claims=(ClaimSpec("built", "Artifact exists", "local", ("artifact",)),),
            runtime_kind="none",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "dist").mkdir()
            (root / "dist" / "demo.whl").write_bytes(b"wheel")
            report = execute_verification_suite(suite, root, FakeProvider())
        artifact = report["gates"][0]["observed"]["artifacts"][0]
        self.assertEqual(artifact["path"], "dist/demo.whl")
        self.assertEqual(len(artifact["sha256"]), 64)

    def test_claim_cannot_reference_unknown_gate(self) -> None:
        suite = VerificationSuite(
            id="broken",
            version="0.1",
            scope="unit",
            gates=(),
            claims=(ClaimSpec("c1", "Impossible", "unit", ("missing",)),),
            runtime_kind="none",
        )
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(VerificationError):
                execute_verification_suite(suite, Path(tmp), FakeProvider())

    def test_mcp_suite_keeps_live_host_unverified_and_does_not_treat_inspector_as_a_gate(self) -> None:
        suite = build_verification_suite("python-mcp-server", "echo-mcp-server", FakeProvider(executable="uv"))
        claims = {claim.id: claim for claim in suite.claims}
        self.assertEqual(claims["live-host"].gate_ids, ())
        self.assertIsNotNone(claims["live-host"].limitation)
        self.assertTrue(any("inspector" in item.lower() or "mcp dev" in item.lower() for item in suite.limitations))
        self.assertNotIn("mcp-host", suite.id)

    def test_vite_web_suite_playwright_gate_is_optional(self) -> None:
        suite = build_verification_suite("typescript-web-ui", "status-board", FakeProvider(executable="npm"))
        claims = {claim.id: claim for claim in suite.claims}
        gates = {gate.id: gate for gate in suite.gates}
        self.assertEqual(claims["browser-runtime"].gate_ids, ("playwright-e2e",))
        self.assertFalse(gates["playwright-e2e"].required)
        self.assertTrue(any("react" in item.lower() or "next" in item.lower() for item in suite.limitations))
        self.assertTrue(any("playwright" in item.lower() for item in suite.limitations))

    def test_optional_failed_gate_keeps_claim_unverified(self) -> None:
        suite = VerificationSuite(
            id="optional",
            version="0.1",
            scope="unit",
            gates=(
                GateSpec("g1", "probe", "command", (sys.executable, "-c", "print('ok')"), ("ok",)),
                GateSpec(
                    "g2",
                    "optional runtime",
                    "command",
                    (sys.executable, "-c", "raise SystemExit(7)"),
                    required=False,
                ),
            ),
            claims=(
                ClaimSpec("verified", "Local probe works", "local", ("g1",)),
                ClaimSpec("external", "External runtime works", "external", ("g2",)),
            ),
            runtime_kind="none",
        )
        with tempfile.TemporaryDirectory() as tmp:
            report = execute_verification_suite(suite, Path(tmp), FakeProvider())
        self.assertTrue(report["required_gates_passed"])
        self.assertEqual(report["status"], "PARTIALLY_VERIFIED")
        self.assertEqual(report["claims"][0]["status"], "VERIFIED")
        self.assertEqual(report["claims"][1]["status"], "UNVERIFIED")
        assert_required_gates(report)

    def test_avalonia_suite_does_not_claim_a_shown_window(self) -> None:
        suite = build_verification_suite(
            "csharp-desktop-avalonia", "tray-helper-avalonia", FakeProvider(executable="dotnet")
        )
        claims = {claim.id: claim for claim in suite.claims}
        self.assertEqual(claims["window-shown"].gate_ids, ())
        self.assertTrue(any("electron" in item.lower() for item in suite.limitations))

    def test_wpf_suite_does_not_claim_a_shown_window(self) -> None:
        suite = build_verification_suite("csharp-desktop", "tray-helper-wpf", FakeProvider(executable="dotnet"))
        claims = {claim.id: claim for claim in suite.claims}
        self.assertEqual(claims["window-shown"].gate_ids, ())
        self.assertTrue(any("electron" in item.lower() for item in suite.limitations))

    def test_rust_library_suite_does_not_claim_crates_io_publish(self) -> None:
        suite = build_verification_suite("rust-library", "string-tools-rs", FakeProvider(executable="cargo"))
        claims = {claim.id: claim for claim in suite.claims}
        self.assertEqual(claims["crates-io-publish"].gate_ids, ())
        self.assertTrue(any("crates.io" in item.lower() for item in suite.limitations))
        self.assertTrue(any("maturin" in item.lower() for item in suite.limitations))

    def test_notebook_suite_keeps_jupyter_lab_unverified(self) -> None:
        suite = build_verification_suite("python-notebook", "repro-notebook", FakeProvider(executable="uv"))
        claims = {claim.id: claim for claim in suite.claims}
        self.assertEqual(claims["jupyter-lab-runtime"].gate_ids, ())
        self.assertTrue(any("jupyter" in item.lower() for item in suite.limitations))

    def test_aspnet_suite_does_not_bind_a_port(self) -> None:
        suite = build_verification_suite("csharp-http-service", "health-api-aspnet", FakeProvider(executable="dotnet"))
        claims = {claim.id: claim for claim in suite.claims}
        self.assertEqual(claims["live-http"].gate_ids, ())
        self.assertTrue(any("kestrel" in item.lower() or "full-stack" in item.lower() for item in suite.limitations))

    def test_http_service_suite_does_not_bind_a_port(self) -> None:
        suite = build_verification_suite("python-http-service", "health-api", FakeProvider(executable="uv"))
        claims = {claim.id: claim for claim in suite.claims}
        self.assertEqual(claims["live-http"].gate_ids, ())
        self.assertTrue(any("full-stack" in item.lower() or "uvicorn" in item.lower() for item in suite.limitations))

    def test_vscode_suite_does_not_launch_vscode(self) -> None:
        suite = build_verification_suite("vscode-extension", "hello-vscode", FakeProvider(executable="npm"))
        claims = {claim.id: claim for claim in suite.claims}
        self.assertEqual(claims["vscode-runtime"].gate_ids, ())
        self.assertEqual(claims["marketplace-publish"].gate_ids, ())

    def test_github_action_suite_does_not_claim_hosted_runners(self) -> None:
        suite = build_verification_suite("github-action", "hello-gha", FakeProvider(executable="npm"))
        claims = {claim.id: claim for claim in suite.claims}
        self.assertEqual(claims["github-runtime"].gate_ids, ())

    def test_docs_site_suite_does_not_serve(self) -> None:
        suite = build_verification_suite("python-docs-site", "docs-home", FakeProvider(executable="uv"))
        claims = {claim.id: claim for claim in suite.claims}
        self.assertEqual(claims["docs-serve"].gate_ids, ())

    def test_astro_suite_does_not_preview(self) -> None:
        suite = build_verification_suite("typescript-static-astro", "static-home", FakeProvider(executable="npm"))
        claims = {claim.id: claim for claim in suite.claims}
        self.assertEqual(claims["site-preview"].gate_ids, ())

    def test_rust_cli_suite_does_not_claim_crates_io_publish(self) -> None:
        suite = build_verification_suite("rust-cli", "hello-clap", FakeProvider(executable="cargo"))
        claims = {claim.id: claim for claim in suite.claims}
        self.assertEqual(claims["crates-io-publish"].gate_ids, ())

    def test_axum_suite_does_not_bind_a_port(self) -> None:
        suite = build_verification_suite("rust-http-service", "health-api-axum", FakeProvider(executable="cargo"))
        claims = {claim.id: claim for claim in suite.claims}
        self.assertEqual(claims["live-http"].gate_ids, ())

    def test_tui_suite_does_not_launch_the_terminal(self) -> None:
        suite = build_verification_suite("python-tui", "status-tui", FakeProvider(executable="uv"))
        claims = {claim.id: claim for claim in suite.claims}
        self.assertEqual(claims["tui-runtime"].gate_ids, ())

    def test_lambda_suite_does_not_claim_aws_runtime(self) -> None:
        suite = build_verification_suite("python-lambda", "hello-lambda", FakeProvider(executable="uv"))
        claims = {claim.id: claim for claim in suite.claims}
        self.assertEqual(claims["aws-runtime"].gate_ids, ())

    def test_cloudflare_worker_suite_does_not_deploy(self) -> None:
        suite = build_verification_suite("cloudflare-worker", "hello-worker", FakeProvider(executable="npm"))
        claims = {claim.id: claim for claim in suite.claims}
        self.assertEqual(claims["cloudflare-runtime"].gate_ids, ())

    def test_playwright_suite_browser_gate_is_optional(self) -> None:
        suite = build_verification_suite("playwright-test-suite", "e2e-suite", FakeProvider(executable="npm"))
        claims = {claim.id: claim for claim in suite.claims}
        gates = {gate.id: gate for gate in suite.gates}
        self.assertEqual(claims["browser-runtime"].gate_ids, ("playwright-e2e",))
        self.assertFalse(gates["playwright-e2e"].required)

    def test_typescript_cli_suite_does_not_publish(self) -> None:
        suite = build_verification_suite("typescript-cli", "hello-commander", FakeProvider(executable="npm"))
        claims = {claim.id: claim for claim in suite.claims}
        self.assertEqual(claims["npm-publish"].gate_ids, ())

    def test_typescript_mcp_suite_does_not_launch_a_host(self) -> None:
        suite = build_verification_suite("typescript-mcp-server", "echo-ts-mcp", FakeProvider(executable="npm"))
        claims = {claim.id: claim for claim in suite.claims}
        self.assertEqual(claims["live-host"].gate_ids, ())

    def test_data_pipeline_suite_does_not_schedule(self) -> None:
        suite = build_verification_suite("python-data-pipeline", "nightly-etl", FakeProvider(executable="uv"))
        claims = {claim.id: claim for claim in suite.claims}
        self.assertEqual(claims["scheduler-runtime"].gate_ids, ())

    def test_alembic_suite_does_not_claim_postgres(self) -> None:
        suite = build_verification_suite("python-schema-migration", "schema-home", FakeProvider(executable="uv"))
        claims = {claim.id: claim for claim in suite.claims}
        self.assertEqual(claims["postgres-migrate"].gate_ids, ())

    def test_openapi_sdk_suite_does_not_call_a_live_api(self) -> None:
        suite = build_verification_suite("typescript-generated-sdk", "health-client", FakeProvider(executable="npm"))
        claims = {claim.id: claim for claim in suite.claims}
        self.assertEqual(claims["live-api"].gate_ids, ())

    def test_eval_harness_suite_does_not_train(self) -> None:
        suite = build_verification_suite("python-eval-harness", "score-home", FakeProvider(executable="uv"))
        claims = {claim.id: claim for claim in suite.claims}
        self.assertEqual(claims["model-runtime"].gate_ids, ())

    def test_bot_suite_does_not_login(self) -> None:
        suite = build_verification_suite("python-bot", "hello-bot", FakeProvider(executable="uv"))
        claims = {claim.id: claim for claim in suite.claims}
        self.assertEqual(claims["gateway-runtime"].gate_ids, ())

    def test_scraper_suite_does_not_fetch_live(self) -> None:
        suite = build_verification_suite("python-scraper", "page-scraper", FakeProvider(executable="uv"))
        claims = {claim.id: claim for claim in suite.claims}
        self.assertEqual(claims["live-fetch"].gate_ids, ())

    def test_hono_suite_does_not_bind_a_port(self) -> None:
        suite = build_verification_suite("typescript-http-hono", "health-hono", FakeProvider(executable="npm"))
        claims = {claim.id: claim for claim in suite.claims}
        self.assertEqual(claims["live-http"].gate_ids, ())

    def test_graphql_suite_does_not_bind_a_port(self) -> None:
        suite = build_verification_suite("typescript-graphql", "status-graphql", FakeProvider(executable="npm"))
        claims = {claim.id: claim for claim in suite.claims}
        self.assertEqual(claims["live-http"].gate_ids, ())

    def test_realtime_suite_does_not_bind_a_port(self) -> None:
        suite = build_verification_suite("python-realtime", "status-ws", FakeProvider(executable="uv"))
        claims = {claim.id: claim for claim in suite.claims}
        self.assertEqual(claims["live-http"].gate_ids, ())

    def test_schema_contract_suite_does_not_hit_a_server(self) -> None:
        suite = build_verification_suite("python-schema-contract", "api-contract", FakeProvider(executable="uv"))
        claims = {claim.id: claim for claim in suite.claims}
        self.assertEqual(claims["live-spec"].gate_ids, ())

    def test_agent_workflow_suite_does_not_call_an_llm(self) -> None:
        suite = build_verification_suite("python-agent-workflow", "echo-workflow", FakeProvider(executable="uv"))
        claims = {claim.id: claim for claim in suite.claims}
        self.assertEqual(claims["llm-runtime"].gate_ids, ())

    def test_design_system_suite_does_not_open_storybook(self) -> None:
        suite = build_verification_suite("typescript-design-system", "token-kit", FakeProvider(executable="npm"))
        claims = {claim.id: claim for claim in suite.claims}
        self.assertEqual(claims["visual-review"].gate_ids, ())

    def test_experiment_suite_does_not_train(self) -> None:
        suite = build_verification_suite("python-experiment", "seeded-run", FakeProvider(executable="uv"))
        claims = {claim.id: claim for claim in suite.claims}
        self.assertEqual(claims["training-runtime"].gate_ids, ())

    def test_nest_suite_does_not_bind_a_port(self) -> None:
        suite = build_verification_suite("typescript-http-nest", "health-nest", FakeProvider(executable="npm"))
        claims = {claim.id: claim for claim in suite.claims}
        self.assertEqual(claims["live-http"].gate_ids, ())

    def test_dbt_suite_does_not_claim_a_warehouse(self) -> None:
        suite = build_verification_suite("python-analytics-dbt", "metrics-dbt", FakeProvider(executable="uv"))
        claims = {claim.id: claim for claim in suite.claims}
        gates = {gate.id: gate for gate in suite.gates}
        self.assertEqual(claims["warehouse-runtime"].gate_ids, ())
        self.assertFalse(gates["dbt-parse"].required)

    def test_rag_suite_does_not_query_a_vector_db(self) -> None:
        suite = build_verification_suite("python-rag", "doc-rag", FakeProvider(executable="uv"))
        claims = {claim.id: claim for claim in suite.claims}
        self.assertEqual(claims["vector-runtime"].gate_ids, ())

    def test_model_serving_suite_does_not_load_gpu_weights(self) -> None:
        suite = build_verification_suite("python-model-serving", "score-serve", FakeProvider(executable="uv"))
        claims = {claim.id: claim for claim in suite.claims}
        self.assertEqual(claims["gpu-runtime"].gate_ids, ())

    def test_compose_stack_suite_does_not_require_docker(self) -> None:
        suite = build_verification_suite("python-container-stack", "compose-home", FakeProvider(executable="uv"))
        claims = {claim.id: claim for claim in suite.claims}
        self.assertEqual(claims["docker-runtime"].gate_ids, ())

    def test_csharp_library_suite_does_not_publish_nuget(self) -> None:
        suite = build_verification_suite("csharp-library", "string-tools-cs", FakeProvider(executable="dotnet"))
        claims = {claim.id: claim for claim in suite.claims}
        self.assertEqual(claims["nuget-publish"].gate_ids, ())

    def test_grpc_suite_does_not_bind_a_port(self) -> None:
        suite = build_verification_suite("python-grpc", "health-grpc", FakeProvider(executable="uv"))
        claims = {claim.id: claim for claim in suite.claims}
        self.assertEqual(claims["live-bind"].gate_ids, ())

    def test_event_driven_suite_does_not_require_a_broker(self) -> None:
        suite = build_verification_suite("python-event-driven", "queue-consumer", FakeProvider(executable="uv"))
        claims = {claim.id: claim for claim in suite.claims}
        self.assertEqual(claims["broker-runtime"].gate_ids, ())

    def test_observability_suite_does_not_require_a_collector(self) -> None:
        suite = build_verification_suite("python-observability", "otel-probe", FakeProvider(executable="uv"))
        claims = {claim.id: claim for claim in suite.claims}
        self.assertEqual(claims["collector-runtime"].gate_ids, ())

    def test_wxt_suite_keeps_real_browser_claims_unverified(self) -> None:
        suite = build_verification_suite("browser-extension-wxt", "demo-wxt", FakeProvider(executable="npm"))
        claims = {claim.id: claim for claim in suite.claims}
        self.assertEqual(claims["chrome-runtime"].gate_ids, ())
        self.assertEqual(claims["firefox-runtime"].gate_ids, ())
        self.assertTrue(any("wxt (dev mode)" in item.lower() or "dev mode" in item.lower() for item in suite.limitations))

    def test_browser_suite_explicitly_keeps_real_browser_claims_unverified(self) -> None:
        provider = FakeProvider(executable="npm")
        suite = build_verification_suite("browser-extension-js", "demo", provider)
        claims = {claim.id: claim for claim in suite.claims}
        self.assertEqual(claims["chrome-runtime"].gate_ids, ())
        self.assertEqual(claims["firefox-runtime"].gate_ids, ())
        self.assertIsNotNone(claims["chrome-runtime"].limitation)
        self.assertIsNotNone(claims["firefox-runtime"].limitation)

    def test_python_suite_does_not_claim_public_registry_publish(self) -> None:
        suite = build_verification_suite("python-library", "demo-lib", FakeProvider(executable="uv"))
        statements = "\n".join(claim.statement for claim in suite.claims).lower()
        self.assertNotIn("pypi publication succeeds", statements)
        self.assertTrue(any("pypi" in limitation.lower() for limitation in suite.limitations))

    def test_observed_command_evidence_is_portable(self) -> None:
        suite = VerificationSuite(
            id="portable",
            version="0.1",
            scope="unit",
            gates=(GateSpec("g1", "probe", "command", (sys.executable, "-c", "print('ok')"), ("ok",)),),
            claims=(ClaimSpec("c1", "Probe works", "unit", ("g1",)),),
            runtime_kind="none",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = execute_verification_suite(suite, root, FakeProvider())
            observed = report["gates"][0]["observed"]
            self.assertEqual(observed["cwd"], ".")
            self.assertNotIn(str(root), str(observed))


if __name__ == "__main__":
    unittest.main()
