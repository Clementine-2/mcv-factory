from __future__ import annotations

from ..verification import ClaimSpec, GateSpec, ProviderView, VerificationSuite, _command_gate


def build_typescript_cli_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "npm-ci-offline",
            "offline npm install from lockfile",
            [executable, "ci", "--offline", "--no-fund", "--no-audit"],
        ),
        _command_gate("unit-tests", "local Commander CLI tests", [executable, "test"]),
        GateSpec(
            "cli-artifacts",
            "compiled CLI entry",
            "artifact",
            artifact_patterns=("dist/cli.js",),
            min_artifacts=1,
        ),
    )
    claims = (
        ClaimSpec("tests-pass", "The generated Commander CLI tests pass locally.", "local generated scaffold", ("unit-tests",)),
        ClaimSpec("cli-builds", "The CLI TypeScript entry compiles locally.", "local package build", ("cli-artifacts",)),
        ClaimSpec(
            "npm-publish",
            "The CLI is published to npm.",
            "public registry publication",
            (),
            True,
            "npm publication is outside this verification scope.",
        ),
    )
    return VerificationSuite(
        "typescript-cli",
        "0.1",
        "generated Commander TypeScript CLI scaffold",
        gates,
        claims,
        "node",
        (
            "Public npm publication is outside this verification scope.",
            "This is the TypeScript CLI line; argparse and clap stay on their language roots.",
        ),
    )
