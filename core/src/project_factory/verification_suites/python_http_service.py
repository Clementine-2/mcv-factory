from __future__ import annotations

from ..verification import (
    ClaimSpec,
    GateSpec,
    ProviderView,
    VerificationSuite,
    _command_gate,
    _python_package_name,
)


def build_python_http_service_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    package_name = _python_package_name(project_name)
    executable = provider.executable
    gates = (
        _command_gate(
            "app-imports",
            "generated FastAPI app import",
            [
                executable,
                "--offline",
                "run",
                "python",
                "-c",
                f"from {package_name}.main import app; print('http service scaffold ready')",
            ],
            "http service scaffold ready",
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
        ClaimSpec("app-importable", "The generated FastAPI app imports locally.", "local generated scaffold", ("app-imports",)),
        ClaimSpec("health-endpoint", "The /health endpoint responds in-process via TestClient.", "local generated scaffold", ("unit-tests",)),
        ClaimSpec("package-builds", "The generated scaffold builds a wheel and source distribution locally.", "local package build", ("package-build", "package-artifacts")),
        ClaimSpec(
            "live-http",
            "The service accepts traffic on a bound HTTP port.",
            "external HTTP listener",
            (),
            True,
            "uvicorn was not bound to a port by this suite.",
        ),
    )
    return VerificationSuite(
        "python-http-service",
        "0.1",
        "generated FastAPI HTTP service scaffold",
        gates,
        claims,
        "python",
        (
            "Public deployment and TLS are outside this verification scope.",
            "This is a minimal service profile, not the official FastAPI full-stack template.",
            "A bound uvicorn process is not a verification gate.",
        ),
    )
