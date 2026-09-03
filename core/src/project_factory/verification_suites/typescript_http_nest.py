from __future__ import annotations

from ..verification import ClaimSpec, GateSpec, ProviderView, VerificationSuite, _command_gate


def build_typescript_http_nest_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "npm-ci-offline",
            "offline npm install from lockfile",
            [executable, "ci", "--offline", "--no-fund", "--no-audit"],
        ),
        _command_gate("unit-tests", "in-process Nest health tests", [executable, "test"]),
        GateSpec(
            "app-artifacts",
            "compiled Nest health controller",
            "artifact",
            artifact_patterns=("dist/health.controller.js",),
            min_artifacts=1,
        ),
    )
    claims = (
        ClaimSpec("tests-pass", "The generated Nest health tests pass locally.", "local generated scaffold", ("unit-tests",)),
        ClaimSpec("app-builds", "The Nest app compiles locally.", "local package build", ("app-artifacts",)),
        ClaimSpec(
            "live-http",
            "The service accepts traffic on a bound HTTP port.",
            "external HTTP listener",
            (),
            True,
            "NestFactory.listen was not a verification gate.",
        ),
    )
    return VerificationSuite(
        "typescript-http-nest",
        "0.1",
        "generated NestJS HTTP service scaffold",
        gates,
        claims,
        "node",
        (
            "This is a Nest body on the TypeScript HTTP line. Hono remains the default.",
            "Binding a port is not a verification gate.",
        ),
    )
