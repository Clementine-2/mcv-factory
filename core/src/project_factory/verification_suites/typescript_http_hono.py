from __future__ import annotations

from ..verification import ClaimSpec, GateSpec, ProviderView, VerificationSuite, _command_gate


def build_typescript_http_hono_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "npm-ci-offline",
            "offline npm install from lockfile",
            [executable, "ci", "--offline", "--no-fund", "--no-audit"],
        ),
        _command_gate("unit-tests", "in-process Hono /health tests", [executable, "test"]),
        GateSpec(
            "app-artifacts",
            "compiled Hono app",
            "artifact",
            artifact_patterns=("dist/app.js",),
            min_artifacts=1,
        ),
    )
    claims = (
        ClaimSpec("tests-pass", "The generated Hono health tests pass locally.", "local generated scaffold", ("unit-tests",)),
        ClaimSpec("app-builds", "The Hono app compiles locally.", "local package build", ("app-artifacts",)),
        ClaimSpec(
            "live-http",
            "The service accepts traffic on a bound HTTP port.",
            "external HTTP listener",
            (),
            True,
            "No TCP port was bound by this suite.",
        ),
    )
    return VerificationSuite(
        "typescript-http-hono",
        "0.1",
        "generated Hono HTTP service scaffold",
        gates,
        claims,
        "node",
        (
            "app.request is the local gate. Binding a port is not a verification gate.",
            "This is the TypeScript HTTP line; FastAPI/Axum/ASP.NET stay on their language roots.",
        ),
    )
