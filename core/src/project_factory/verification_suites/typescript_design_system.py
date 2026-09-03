from __future__ import annotations

from ..verification import ClaimSpec, GateSpec, ProviderView, VerificationSuite, _command_gate


def build_typescript_design_system_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "npm-ci-offline",
            "offline npm install from lockfile",
            [executable, "ci", "--offline", "--no-fund", "--no-audit"],
        ),
        _command_gate("unit-tests", "local token tests", [executable, "test"]),
        GateSpec(
            "token-artifacts",
            "compiled tokens and CSS drawing",
            "artifact",
            artifact_patterns=("dist/tokens.js", "src/tokens.css"),
            min_artifacts=2,
        ),
    )
    claims = (
        ClaimSpec("tests-pass", "The generated design-system token tests pass locally.", "local generated scaffold", ("unit-tests",)),
        ClaimSpec("tokens-build", "The token module compiles locally.", "local package build", ("token-artifacts",)),
        ClaimSpec(
            "visual-review",
            "A visual review or Storybook session was completed.",
            "visual review",
            (),
            True,
            "Storybook was not launched by this suite.",
        ),
    )
    return VerificationSuite(
        "typescript-design-system",
        "0.1",
        "generated design-system token scaffold",
        gates,
        claims,
        "node",
        ("This is a token drawing, not a Storybook app and not a TypeScript utility library.",),
    )
