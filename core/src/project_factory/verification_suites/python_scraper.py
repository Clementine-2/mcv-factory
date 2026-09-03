from __future__ import annotations

from ..verification import (
    ClaimSpec,
    GateSpec,
    ProviderView,
    VerificationSuite,
    _command_gate,
    _python_package_name,
)


def build_python_scraper_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    package_name = _python_package_name(project_name)
    executable = provider.executable
    gates = (
        _command_gate(
            "scraper-imports",
            "generated scraper import",
            [
                executable,
                "--offline",
                "run",
                "python",
                "-c",
                f"from {package_name}.scraper import scaffold_status; print(scaffold_status())",
            ],
            "scraper scaffold ready",
        ),
        _command_gate(
            "unit-tests",
            "local unit tests",
            [executable, "--offline", "run", "python", "-m", "unittest", "discover", "-s", "tests", "-v"],
        ),
        _command_gate("package-build", "local Python package build", [executable, "--offline", "build"]),
        GateSpec(
            "package-artifacts",
            "wheel and source distribution artifacts",
            "artifact",
            artifact_patterns=("dist/*.whl", "dist/*.tar.gz"),
            min_artifacts=2,
        ),
    )
    claims = (
        ClaimSpec("scraper-importable", "The generated scraper imports locally.", "local generated scaffold", ("scraper-imports",)),
        ClaimSpec("fixture-parse", "The scraper extracts status from a local HTML fixture.", "local generated scaffold", ("unit-tests",)),
        ClaimSpec("package-builds", "The generated scaffold builds a wheel and source distribution locally.", "local package build", ("package-build", "package-artifacts")),
        ClaimSpec(
            "live-fetch",
            "The scraper fetched a live remote page.",
            "external HTTP fetch",
            (),
            True,
            "No live website was fetched by this suite. This is not Scrapy.",
        ),
    )
    return VerificationSuite(
        "python-scraper",
        "0.1",
        "generated local HTML scraper scaffold",
        gates,
        claims,
        "python",
        (
            "This parses a frozen HTML fixture. Live crawling and Scrapy are outside this verification scope.",
        ),
    )
