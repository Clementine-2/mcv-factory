from __future__ import annotations

from ..verification import ClaimSpec, GateSpec, ProviderView, VerificationSuite, _command_gate


def build_typescript_generated_sdk_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "npm-ci-offline",
            "offline npm install from lockfile",
            [executable, "ci", "--offline", "--no-fund", "--no-audit"],
        ),
        _command_gate("unit-tests", "local generated SDK tests", [executable, "test"]),
        GateSpec(
            "sdk-artifacts",
            "compiled client and OpenAPI drawing",
            "artifact",
            artifact_patterns=("dist/client.js", "openapi.yaml"),
            min_artifacts=2,
        ),
    )
    claims = (
        ClaimSpec("tests-pass", "The generated OpenAPI client tests pass locally.", "local generated scaffold", ("unit-tests",)),
        ClaimSpec("sdk-builds", "The TypeScript client compiles locally.", "local package build", ("sdk-artifacts",)),
        ClaimSpec(
            "live-api",
            "The client called a live upstream HTTP API.",
            "external HTTP API",
            (),
            True,
            "No upstream server was launched by this suite. The OpenAPI document is a frozen drawing.",
        ),
    )
    return VerificationSuite(
        "typescript-generated-sdk",
        "0.1",
        "generated OpenAPI TypeScript client scaffold",
        gates,
        claims,
        "node",
        (
            "The OpenAPI document is frozen in-repo. Live spec drift is outside this verification scope.",
            "Observed latest openapi-typescript is not auto-promoted; this line is pinned.",
        ),
    )
