from __future__ import annotations

from ..verification import (
    ClaimSpec,
    GateSpec,
    ProviderView,
    VerificationSuite,
    _command_gate,
    _python_package_name,
)


def build_python_experiment_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    package_name = _python_package_name(project_name)
    executable = provider.executable
    gates = (
        _command_gate(
            "experiment-imports",
            "generated experiment import",
            [
                executable,
                "--offline",
                "run",
                "python",
                "-c",
                f"from {package_name}.experiment import scaffold_status; print(scaffold_status())",
            ],
            "experiment scaffold ready",
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
        ClaimSpec("experiment-importable", "The generated experiment module imports locally.", "local generated scaffold", ("experiment-imports",)),
        ClaimSpec("run-reproducible", "A seeded run writes results from params.json.", "local generated scaffold", ("unit-tests",)),
        ClaimSpec("package-builds", "The generated scaffold builds a wheel and source distribution locally.", "local package build", ("package-build", "package-artifacts")),
        ClaimSpec(
            "training-runtime",
            "A model was trained.",
            "external training runtime",
            (),
            True,
            "No GPU training job was launched. This is not a Jupyter notebook.",
        ),
    )
    return VerificationSuite(
        "python-experiment",
        "0.1",
        "generated reproducible experiment scaffold",
        gates,
        claims,
        "python",
        ("params.json is the local gate. Notebooks remain a different profile.",),
    )
