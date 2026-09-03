from __future__ import annotations

from ..verification import (
    ClaimSpec,
    GateSpec,
    ProviderView,
    VerificationSuite,
    _command_gate,
    _python_package_name,
)


def build_python_observability_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    package_name = _python_package_name(project_name)
    executable = provider.executable
    gates = (
        _command_gate(
            "probe-imports",
            "generated OpenTelemetry probe import",
            [
                executable,
                "--offline",
                "run",
                "python",
                "-c",
                f"from {package_name}.probe import scaffold_status; print(scaffold_status())",
            ],
            "observability probe scaffold ready",
        ),
        _command_gate(
            "unit-tests",
            "in-memory span exporter tests",
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
        ClaimSpec("probe-importable", "The generated OpenTelemetry probe imports locally.", "local generated scaffold", ("probe-imports",)),
        ClaimSpec("span-recorded", "A span is recorded via the in-memory exporter.", "local generated scaffold", ("unit-tests",)),
        ClaimSpec("package-builds", "The generated scaffold builds a wheel and source distribution locally.", "local package build", ("package-build", "package-artifacts")),
        ClaimSpec(
            "collector-runtime",
            "A collector or sidecar received exported telemetry.",
            "external OpenTelemetry collector",
            (),
            True,
            "No collector process was launched. This is an in-memory probe, not a collector config repo.",
        ),
    )
    return VerificationSuite(
        "python-observability",
        "0.1",
        "generated OpenTelemetry in-memory probe scaffold",
        gates,
        claims,
        "python",
        (
            "OpenTelemetry API/SDK 1.31.1 with InMemorySpanExporter.",
            "A collector, sidecar, or OTLP endpoint is not a verification gate.",
        ),
    )
