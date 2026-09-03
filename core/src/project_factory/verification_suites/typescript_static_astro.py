from __future__ import annotations

from ..verification import ClaimSpec, GateSpec, ProviderView, VerificationSuite, _command_gate


def build_typescript_static_astro_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "npm-ci-offline",
            "offline npm install from lockfile",
            [executable, "ci", "--offline", "--no-fund", "--no-audit"],
        ),
        _command_gate("unit-tests", "local Astro drawing tests", [executable, "test"]),
        _command_gate("astro-build", "Astro production build", [executable, "run", "build"]),
        GateSpec(
            "site-artifacts",
            "built static site",
            "artifact",
            artifact_patterns=("dist/index.html", "dist/**/*.html"),
            min_artifacts=1,
        ),
    )
    claims = (
        ClaimSpec("tests-pass", "The generated Astro smoke tests pass locally.", "local generated scaffold", ("unit-tests",)),
        ClaimSpec("site-builds", "Astro can produce a static dist locally.", "local package build", ("astro-build", "site-artifacts")),
        ClaimSpec(
            "site-preview",
            "The static site was served and browsed.",
            "local HTTP preview",
            (),
            True,
            "astro preview/dev was not launched by this suite.",
        ),
    )
    return VerificationSuite(
        "typescript-static-astro",
        "0.1",
        "generated Astro static site scaffold",
        gates,
        claims,
        "node",
        (
            "astro preview and astro dev open a server and are not verification gates.",
            "Observed latest Astro is not auto-promoted; this line is pinned.",
        ),
    )
