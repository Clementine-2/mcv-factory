from __future__ import annotations

from ..verification import (
    ClaimSpec,
    GateSpec,
    ProviderView,
    VerificationSuite,
    _command_gate,
    _python_package_name,
)


def build_python_analytics_dbt_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    package_name = _python_package_name(project_name)
    executable = provider.executable
    gates = (
        _command_gate(
            "package-imports",
            "generated dbt package import",
            [
                executable,
                "--offline",
                "run",
                "python",
                "-c",
                f"from {package_name} import scaffold_status; print(scaffold_status())",
            ],
            "analytics transform scaffold ready",
        ),
        _command_gate(
            "unit-tests",
            "local drawing tests",
            [executable, "--offline", "run", "python", "-m", "unittest", "discover", "-s", "tests", "-v"],
        ),
        _command_gate(
            "dbt-parse",
            "dbt parse against local DuckDB profile",
            [executable, "--offline", "run", "dbt", "parse", "--project-dir", ".", "--profiles-dir", "."],
            required=False,
            timeout_sec=180,
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
        ClaimSpec("package-importable", "The generated dbt package imports locally.", "local generated scaffold", ("package-imports",)),
        ClaimSpec("dbt-parses", "dbt parse succeeds against the local DuckDB profile.", "local generated scaffold", ("dbt-parse",)),
        ClaimSpec("package-builds", "The generated scaffold builds a wheel and source distribution locally.", "local package build", ("package-build", "package-artifacts")),
        ClaimSpec(
            "warehouse-runtime",
            "Models ran on a live warehouse.",
            "external warehouse",
            (),
            True,
            "Postgres/Snowflake were not launched. DuckDB parse is the local gate.",
        ),
    )
    return VerificationSuite(
        "python-analytics-dbt",
        "0.1",
        "generated dbt analytics-transform scaffold",
        gates,
        claims,
        "python",
        (
            "dbt parse is optional: dbt-core 1.9 may not import on Python 3.14. Drawings still verify.",
            "A remote warehouse is unverified.",
        ),
    )
