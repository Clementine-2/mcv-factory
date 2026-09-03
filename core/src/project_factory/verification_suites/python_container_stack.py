from __future__ import annotations

from ..verification import (
    ClaimSpec,
    GateSpec,
    ProviderView,
    VerificationSuite,
    _command_gate,
    _python_package_name,
)


def build_python_container_stack_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    package_name = _python_package_name(project_name)
    executable = provider.executable
    gates = (
        _command_gate(
            "stack-imports",
            "generated compose loader import",
            [
                executable,
                "--offline",
                "run",
                "python",
                "-c",
                f"from {package_name}.stack import scaffold_status; print(scaffold_status())",
            ],
            "container stack scaffold ready",
        ),
        _command_gate(
            "unit-tests",
            "compose drawing tests",
            [executable, "--offline", "run", "python", "-m", "unittest", "discover", "-s", "tests", "-v"],
        ),
        _command_gate("package-build", "local Python package build", [executable, "--offline", "build"]),
        GateSpec(
            "package-artifacts",
            "wheel, sdist, and compose drawing",
            "artifact",
            artifact_patterns=("dist/*.whl", "dist/*.tar.gz", "compose.yaml"),
            min_artifacts=3,
        ),
    )
    claims = (
        ClaimSpec("stack-importable", "The generated compose loader imports locally.", "local generated scaffold", ("stack-imports",)),
        ClaimSpec("compose-loads", "compose.yaml declares the scaffold service.", "local generated scaffold", ("unit-tests",)),
        ClaimSpec("package-builds", "The generated scaffold builds a wheel and source distribution locally.", "local package build", ("package-build", "package-artifacts")),
        ClaimSpec(
            "docker-runtime",
            "docker compose up ran the stack.",
            "Docker daemon",
            (),
            True,
            "A Docker daemon was not required. The factory does not install Docker.",
        ),
    )
    return VerificationSuite(
        "python-container-stack",
        "0.1",
        "generated Docker Compose stack drawing",
        gates,
        claims,
        "python",
        ("compose.yaml is the local drawing. docker compose up remains unverified.",),
    )
