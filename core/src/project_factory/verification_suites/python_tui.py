from __future__ import annotations

from ..verification import (
    ClaimSpec,
    GateSpec,
    ProviderView,
    VerificationSuite,
    _command_gate,
    _python_package_name,
)


def build_python_tui_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    package_name = _python_package_name(project_name)
    executable = provider.executable
    gates = (
        _command_gate(
            "app-imports",
            "generated Textual app import",
            [
                executable,
                "--offline",
                "run",
                "python",
                "-c",
                f"from {package_name}.app import ScaffoldApp, scaffold_status; print(scaffold_status())",
            ],
            "tui scaffold ready",
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
        ClaimSpec("app-importable", "The generated Textual app imports locally.", "local generated scaffold", ("app-imports",)),
        ClaimSpec("compose-status", "The TUI compose tree exposes the scaffold status widget.", "local generated scaffold", ("unit-tests",)),
        ClaimSpec("package-builds", "The generated scaffold builds a wheel and source distribution locally.", "local package build", ("package-build", "package-artifacts")),
        ClaimSpec(
            "tui-runtime",
            "The interactive terminal UI was shown.",
            "interactive terminal",
            (),
            True,
            "ScaffoldApp.run was not launched by this suite.",
        ),
    )
    return VerificationSuite(
        "python-tui",
        "0.1",
        "generated Textual TUI scaffold",
        gates,
        claims,
        "python",
        (
            "Launching an interactive terminal UI is not a verification gate.",
            "Observed latest Textual is not auto-promoted; this line is pinned.",
        ),
    )
