from __future__ import annotations

from ..verification import ClaimSpec, GateSpec, ProviderView, VerificationSuite, _command_gate


def build_typescript_web_ui_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "npm-ci-offline",
            "offline npm install from lockfile",
            [executable, "ci", "--offline", "--no-fund", "--no-audit"],
        ),
        _command_gate("unit-tests", "local Node tests", [executable, "test"]),
        _command_gate("vite-build", "Vite production build", [executable, "run", "build"]),
        GateSpec(
            "web-artifacts",
            "built web assets",
            "artifact",
            artifact_patterns=("dist/index.html", "dist/**/*.js"),
            min_artifacts=1,
        ),
        _command_gate(
            "playwright-e2e",
            "Playwright true-browser smoke against the production preview",
            [executable, "run", "test:e2e"],
            "passed",
            required=False,
            timeout_sec=180,
        ),
    )
    claims = (
        ClaimSpec("tests-pass", "The generated Vite smoke tests pass locally.", "local generated scaffold", ("unit-tests",)),
        ClaimSpec("frontend-builds", "Vite can produce a production dist locally.", "local package build", ("vite-build", "web-artifacts")),
        ClaimSpec(
            "browser-runtime",
            "The page was opened in a real browser.",
            "browser runtime",
            ("playwright-e2e",),
            True,
            "VERIFIED only when Playwright actually launches a system browser. Missing browsers stay UNVERIFIED. vite preview/dev is not itself a verification gate.",
        ),
    )
    return VerificationSuite(
        "typescript-web-ui",
        "0.1",
        "generated Vite TypeScript web UI scaffold",
        gates,
        claims,
        "node",
        (
            "This is a vanilla TypeScript Vite app, not React/Next/Vue.",
            "vite dev and vite preview open a server/browser and are not verification gates.",
            "Playwright uses the installed Chrome/Edge channel; browsers are not downloaded by the factory.",
            "Observed latest Vite/TypeScript is not auto-promoted; this line is pinned.",
        ),
    )
