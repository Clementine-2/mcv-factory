from __future__ import annotations

from ..verification import ClaimSpec, GateSpec, ProviderView, VerificationSuite, _command_gate


def build_github_action_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "npm-ci-offline",
            "offline npm install from lockfile",
            [executable, "ci", "--offline", "--no-fund", "--no-audit"],
        ),
        _command_gate("unit-tests", "local GitHub Action smoke tests", [executable, "test"]),
        GateSpec(
            "action-artifacts",
            "compiled action entry and metadata",
            "artifact",
            artifact_patterns=("dist/index.js", "action.yml"),
            min_artifacts=2,
        ),
    )
    claims = (
        ClaimSpec("tests-pass", "The generated GitHub Action smoke tests pass locally.", "local generated scaffold", ("unit-tests",)),
        ClaimSpec("action-builds", "The Node 20 action entry compiles locally.", "local package build", ("action-artifacts",)),
        ClaimSpec(
            "github-runtime",
            "The action ran on a GitHub-hosted runner.",
            "GitHub Actions runtime",
            (),
            True,
            "GitHub-hosted runners were not launched by this suite.",
        ),
    )
    return VerificationSuite(
        "github-action",
        "0.1",
        "generated GitHub Action scaffold",
        gates,
        claims,
        "node",
        (
            "Local compile and smoke tests are verified; GitHub-hosted execution remains unverified.",
        ),
    )
