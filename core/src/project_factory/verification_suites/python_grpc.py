from __future__ import annotations

from ..verification import (
    ClaimSpec,
    GateSpec,
    ProviderView,
    VerificationSuite,
    _command_gate,
    _python_package_name,
)


def build_python_grpc_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    package_name = _python_package_name(project_name)
    executable = provider.executable
    gates = (
        _command_gate(
            "servicer-imports",
            "generated gRPC servicer import",
            [
                executable,
                "--offline",
                "run",
                "python",
                "-c",
                f"from {package_name}.servicer import scaffold_status; print(scaffold_status())",
            ],
            "grpc scaffold ready",
        ),
        _command_gate(
            "unit-tests",
            "in-process servicer tests",
            [executable, "--offline", "run", "python", "-m", "unittest", "discover", "-s", "tests", "-v"],
        ),
        _command_gate("package-build", "local Python package build", [executable, "--offline", "build"]),
        GateSpec(
            "package-artifacts",
            "wheel, sdist, and proto drawing",
            "artifact",
            artifact_patterns=("dist/*.whl", "dist/*.tar.gz", "status.proto"),
            min_artifacts=3,
        ),
    )
    claims = (
        ClaimSpec("servicer-importable", "The generated gRPC servicer imports locally.", "local generated scaffold", ("servicer-imports",)),
        ClaimSpec("say-status", "SayStatus returns in-process without binding a port.", "local generated scaffold", ("unit-tests",)),
        ClaimSpec("package-builds", "The generated scaffold builds a wheel and source distribution locally.", "local package build", ("package-build", "package-artifacts")),
        ClaimSpec(
            "live-bind",
            "A gRPC server accepted traffic on a bound port.",
            "external gRPC listener",
            (),
            True,
            "No gRPC port was bound by this suite.",
        ),
    )
    return VerificationSuite(
        "python-grpc",
        "0.1",
        "generated in-process gRPC servicer scaffold",
        gates,
        claims,
        "python",
        (
            "status.proto is the frozen drawing. A bound grpcio server is not a verification gate.",
            "This is not a generated client SDK.",
        ),
    )
