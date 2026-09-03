from __future__ import annotations

from ..verification import ClaimSpec, GateSpec, ProviderView, VerificationSuite, _command_gate


def build_rust_http_service_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "crate-tests",
            "generated Axum unit tests",
            [executable, "test", "--offline"],
            "test result: ok",
            timeout_sec=600,
        ),
        _command_gate(
            "crate-build",
            "generated Axum service build",
            [executable, "build", "--offline"],
            "Finished",
            timeout_sec=600,
        ),
        GateSpec(
            "crate-artifacts",
            "compiled service artifacts",
            "artifact",
            artifact_patterns=(
                "target/debug/*.rlib",
                "target/debug/*.lib",
                "target/debug/*.exe",
                "target/debug/lib*.rlib",
            ),
            min_artifacts=1,
        ),
    )
    claims = (
        ClaimSpec("health-endpoint", "The /health endpoint responds in-process via oneshot.", "local generated scaffold", ("crate-tests",)),
        ClaimSpec("crate-builds", "The generated Axum service compiles locally.", "local generated scaffold", ("crate-build", "crate-artifacts")),
        ClaimSpec(
            "live-http",
            "The service accepts traffic on a bound HTTP port.",
            "external HTTP listener",
            (),
            True,
            "axum::serve was not bound to a port by this suite.",
        ),
    )
    return VerificationSuite(
        "rust-http-service",
        "0.1",
        "generated Axum HTTP service scaffold",
        gates,
        claims,
        "rust",
        (
            "Public deployment and TLS are outside this verification scope.",
            "Binding a TCP port is not a verification gate.",
            "axum's tokio/net features are not enabled: this Windows GNU host cannot compile windows-sys (dlltool missing), same limit as iced.",
            "Observed latest Axum is not auto-promoted; this line is pinned.",
        ),
    )
