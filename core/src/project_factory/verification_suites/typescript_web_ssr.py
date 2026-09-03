from __future__ import annotations

from ..verification import ClaimSpec, GateSpec, ProviderView, VerificationSuite, _command_gate


def build_typescript_web_ssr_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "npm-ci-offline",
            "offline npm install from lockfile",
            [executable, "ci", "--offline", "--no-fund", "--no-audit"],
        ),
        _command_gate("unit-tests", "local Node tests", [executable, "test"]),
        _command_gate("next-build", "Next.js production build", [executable, "run", "build"]),
        GateSpec(
            "ssr-artifacts",
            "Next.js build output",
            "artifact",
            artifact_patterns=(".next/BUILD_ID", ".next/**/page.js", ".next/**/*.html"),
            min_artifacts=1,
        ),
    )
    claims = (
        ClaimSpec("tests-pass", "The generated Next.js smoke tests pass locally.", "local generated scaffold", ("unit-tests",)),
        ClaimSpec("frontend-builds", "Next.js can produce a production build locally.", "local package build", ("next-build", "ssr-artifacts")),
        ClaimSpec(
            "server-runtime",
            "The app served HTTP from next start or next dev.",
            "local HTTP server",
            (),
            True,
            "next dev/start were not launched. A bound port is not a verification gate.",
        ),
        ClaimSpec(
            "browser-runtime",
            "The page was opened in a real browser.",
            "browser runtime",
            (),
            True,
            "A browser was not launched by this suite.",
        ),
    )
    return VerificationSuite(
        "typescript-web-ssr",
        "0.1",
        "generated Next.js TypeScript web scaffold",
        gates,
        claims,
        "node",
        (
            "This is a pinned Next 15 App Router scaffold, not create-next-app latest.",
            "next dev and next start bind a port and are not verification gates.",
            "Observed latest Next 16 is not auto-promoted.",
        ),
    )
