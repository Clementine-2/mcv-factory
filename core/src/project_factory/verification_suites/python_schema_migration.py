from __future__ import annotations

from ..verification import (
    ClaimSpec,
    GateSpec,
    ProviderView,
    VerificationSuite,
    _command_gate,
    _python_package_name,
)


def build_python_schema_migration_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    package_name = _python_package_name(project_name)
    executable = provider.executable
    gates = (
        _command_gate(
            "package-imports",
            "generated migration package import",
            [
                executable,
                "--offline",
                "run",
                "python",
                "-c",
                f"from {package_name} import scaffold_status; print(scaffold_status())",
            ],
            "schema migration scaffold ready",
        ),
        _command_gate(
            "unit-tests",
            "SQLite Alembic upgrade tests",
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
        ClaimSpec("package-importable", "The generated migration package imports locally.", "local generated scaffold", ("package-imports",)),
        ClaimSpec("sqlite-upgrade", "Alembic upgrade head applies against SQLite.", "local generated scaffold", ("unit-tests",)),
        ClaimSpec("package-builds", "The generated scaffold builds a wheel and source distribution locally.", "local package build", ("package-build", "package-artifacts")),
        ClaimSpec(
            "postgres-migrate",
            "Migrations ran against a live Postgres.",
            "external database",
            (),
            True,
            "Postgres was not launched by this suite.",
        ),
    )
    return VerificationSuite(
        "python-schema-migration",
        "0.1",
        "generated Alembic schema-migration scaffold",
        gates,
        claims,
        "python",
        (
            "SQLite is the local gate. Postgres/MySQL migrate remains unverified.",
            "Observed latest Alembic/SQLAlchemy is not auto-promoted; this line is pinned.",
        ),
    )
