from __future__ import annotations

from ..verification import (
    ClaimSpec,
    GateSpec,
    ProviderView,
    VerificationSuite,
    _command_gate,
    _python_package_name,
)


def build_python_schema_contract_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    package_name = _python_package_name(project_name)
    executable = provider.executable
    gates = (
        _command_gate(
            "contract-imports",
            "generated contract loader import",
            [
                executable,
                "--offline",
                "run",
                "python",
                "-c",
                f"from {package_name}.contract import scaffold_status; print(scaffold_status())",
            ],
            "schema contract scaffold ready",
        ),
        _command_gate(
            "unit-tests",
            "OpenAPI drawing tests",
            [executable, "--offline", "run", "python", "-m", "unittest", "discover", "-s", "tests", "-v"],
        ),
        _command_gate("package-build", "local Python package build", [executable, "--offline", "build"]),
        GateSpec(
            "package-artifacts",
            "wheel and source distribution artifacts",
            "artifact",
            artifact_patterns=("dist/*.whl", "dist/*.tar.gz", "openapi.yaml"),
            min_artifacts=3,
        ),
    )
    claims = (
        ClaimSpec("contract-importable", "The generated contract loader imports locally.", "local generated scaffold", ("contract-imports",)),
        ClaimSpec("spec-loads", "The frozen OpenAPI drawing loads and exposes /health.", "local generated scaffold", ("unit-tests",)),
        ClaimSpec("package-builds", "The generated scaffold builds a wheel and source distribution locally.", "local package build", ("package-build", "package-artifacts")),
        ClaimSpec(
            "live-spec",
            "The contract was checked against a live implementing server.",
            "external HTTP API",
            (),
            True,
            "No implementing server was launched. This is a contract repo, not a generated SDK.",
        ),
    )
    return VerificationSuite(
        "python-schema-contract",
        "0.1",
        "generated OpenAPI schema-contract scaffold",
        gates,
        claims,
        "python",
        ("The OpenAPI document is frozen in-repo. Generated clients are a different profile.",),
    )
