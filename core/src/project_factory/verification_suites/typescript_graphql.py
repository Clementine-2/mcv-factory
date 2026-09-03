from __future__ import annotations

from ..verification import ClaimSpec, GateSpec, ProviderView, VerificationSuite, _command_gate


def build_typescript_graphql_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "npm-ci-offline",
            "offline npm install from lockfile",
            [executable, "ci", "--offline", "--no-fund", "--no-audit"],
        ),
        _command_gate("unit-tests", "in-process GraphQL execute tests", [executable, "test"]),
        GateSpec(
            "schema-artifacts",
            "compiled GraphQL schema module",
            "artifact",
            artifact_patterns=("dist/schema.js",),
            min_artifacts=1,
        ),
    )
    claims = (
        ClaimSpec("tests-pass", "The generated GraphQL status query executes locally.", "local generated scaffold", ("unit-tests",)),
        ClaimSpec("schema-builds", "The GraphQL schema module compiles locally.", "local package build", ("schema-artifacts",)),
        ClaimSpec(
            "live-http",
            "The GraphQL HTTP server accepted traffic.",
            "external HTTP listener",
            (),
            True,
            "No GraphQL HTTP listener was bound by this suite.",
        ),
    )
    return VerificationSuite(
        "typescript-graphql",
        "0.1",
        "generated GraphQL API scaffold",
        gates,
        claims,
        "node",
        (
            "graphql() in-process is the local gate. Apollo/Yoga servers are not launched.",
        ),
    )
