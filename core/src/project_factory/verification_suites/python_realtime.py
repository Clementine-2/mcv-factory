from __future__ import annotations

from ..verification import (
    ClaimSpec,
    GateSpec,
    ProviderView,
    VerificationSuite,
    _command_gate,
    _python_package_name,
)


def build_python_realtime_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    package_name = _python_package_name(project_name)
    executable = provider.executable
    gates = (
        _command_gate(
            "app-imports",
            "generated realtime app import",
            [
                executable,
                "--offline",
                "run",
                "python",
                "-c",
                f"from {package_name}.app import scaffold_status; print(scaffold_status())",
            ],
            "realtime scaffold ready",
        ),
        _command_gate(
            "unit-tests",
            "in-process WebSocket tests",
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
        ClaimSpec("app-importable", "The generated realtime app imports locally.", "local generated scaffold", ("app-imports",)),
        ClaimSpec("websocket-status", "The /ws handler returns status in-process.", "local generated scaffold", ("unit-tests",)),
        ClaimSpec("package-builds", "The generated scaffold builds a wheel and source distribution locally.", "local package build", ("package-build", "package-artifacts")),
        ClaimSpec(
            "live-http",
            "A WebSocket server accepted traffic on a bound port.",
            "external WebSocket listener",
            (),
            True,
            "No TCP port was bound by this suite.",
        ),
    )
    return VerificationSuite(
        "python-realtime",
        "0.1",
        "generated Starlette WebSocket scaffold",
        gates,
        claims,
        "python",
        ("Starlette TestClient is the local gate. Binding a port is not a verification gate.",),
    )
