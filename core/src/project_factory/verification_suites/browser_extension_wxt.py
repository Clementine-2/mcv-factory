from __future__ import annotations

from ..verification import ClaimSpec, GateSpec, ProviderView, VerificationSuite, _command_gate


def build_browser_extension_wxt_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "npm-ci-offline",
            "offline npm install from lockfile",
            [executable, "ci", "--offline", "--no-fund", "--no-audit"],
        ),
        _command_gate("unit-tests", "local Node tests", [executable, "test"]),
        _command_gate("wxt-zip", "WXT extension zip", [executable, "run", "zip"]),
        GateSpec(
            "extension-zip",
            "built extension zip artifact",
            "artifact",
            artifact_patterns=(".output/**/*.zip",),
            min_artifacts=1,
        ),
    )
    claims = (
        ClaimSpec("tests-pass", "The generated WXT smoke tests pass locally.", "local generated scaffold", ("unit-tests",)),
        ClaimSpec("extension-zipped", "WXT can produce an extension zip locally.", "local package build", ("wxt-zip", "extension-zip")),
        ClaimSpec(
            "chrome-runtime",
            "The extension works in a real Chrome runtime.",
            "Chrome runtime",
            (),
            True,
            "Chrome was not launched by this suite.",
        ),
        ClaimSpec(
            "firefox-runtime",
            "The extension works in a real Firefox runtime.",
            "Firefox runtime",
            (),
            True,
            "Firefox was not launched by this suite. wxt -b firefox was not used as a verification gate.",
        ),
    )
    return VerificationSuite(
        "browser-extension-wxt",
        "0.1",
        "generated WXT browser-extension scaffold",
        gates,
        claims,
        "node",
        (
            "WXT build/zip is verified; real Chrome and Firefox runtime compatibility remain unverified.",
            "wxt (dev mode) opens a browser and is not a verification gate.",
            "The previous hand-written Manifest V3 profile remains available for JavaScript requests.",
        ),
    )
