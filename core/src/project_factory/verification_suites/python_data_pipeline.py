from __future__ import annotations

from ..verification import (
    ClaimSpec,
    GateSpec,
    ProviderView,
    VerificationSuite,
    _command_gate,
    _python_package_name,
)


def build_python_data_pipeline_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    package_name = _python_package_name(project_name)
    executable = provider.executable
    gates = (
        _command_gate(
            "pipeline-imports",
            "generated pipeline import",
            [
                executable,
                "--offline",
                "run",
                "python",
                "-c",
                f"from {package_name}.pipeline import scaffold_status; print(scaffold_status())",
            ],
            "data pipeline scaffold ready",
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
        ClaimSpec("pipeline-importable", "The generated pipeline imports locally.", "local generated scaffold", ("pipeline-imports",)),
        ClaimSpec("transform-ok", "The transform writes stamped output in-process.", "local generated scaffold", ("unit-tests",)),
        ClaimSpec("package-builds", "The generated scaffold builds a wheel and source distribution locally.", "local package build", ("package-build", "package-artifacts")),
        ClaimSpec(
            "scheduler-runtime",
            "The pipeline ran on a cron/orchestrator schedule.",
            "external scheduler",
            (),
            True,
            "cron, Dagster, and Airflow were not launched by this suite.",
        ),
    )
    return VerificationSuite(
        "python-data-pipeline",
        "0.1",
        "generated Python data-pipeline scaffold",
        gates,
        claims,
        "python",
        (
            "This is a minimal transform pipeline, not Dagster or Airflow.",
            "A scheduler is not a verification gate.",
        ),
    )
