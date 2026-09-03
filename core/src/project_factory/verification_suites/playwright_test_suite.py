from __future__ import annotations

from ..verification import ClaimSpec, ProviderView, VerificationSuite, _command_gate


def build_playwright_test_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "npm-ci-offline",
            "offline npm install from lockfile",
            [executable, "ci", "--offline", "--no-fund", "--no-audit"],
        ),
        _command_gate("unit-tests", "local Playwright suite drawing tests", [executable, "test"]),
        _command_gate(
            "playwright-e2e",
            "Playwright true-browser smoke against the fixture page",
            [executable, "run", "test:e2e"],
            "passed",
            required=False,
            timeout_sec=180,
        ),
    )
    claims = (
        ClaimSpec("tests-pass", "The generated Playwright suite smoke tests pass locally.", "local generated scaffold", ("unit-tests",)),
        ClaimSpec(
            "browser-runtime",
            "The fixture page was opened in a real browser.",
            "browser runtime",
            ("playwright-e2e",),
            True,
            "VERIFIED only when Playwright actually launches a system browser. Missing browsers stay UNVERIFIED. Browsers are not downloaded by the factory.",
        ),
    )
    return VerificationSuite(
        "playwright-test-suite",
        "0.1",
        "generated standalone Playwright test-suite scaffold",
        gates,
        claims,
        "node",
        (
            "This is a standalone test-suite profile, not a Vite/Astro web UI.",
            "Playwright uses the installed Chrome/Edge channel; browsers are not downloaded by the factory.",
            "Observed latest Playwright is not auto-promoted; this line is pinned.",
        ),
    )
