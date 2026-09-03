from __future__ import annotations

from ..verification import (
    ClaimSpec,
    GateSpec,
    ProviderView,
    VerificationSuite,
    _command_gate,
    _python_package_name,
)


def build_python_notebook_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    package_name = _python_package_name(project_name)
    executable = provider.executable
    gates = (
        _command_gate(
            "notebook-format",
            "generated notebook is nbformat 4",
            [
                executable,
                "--offline",
                "run",
                "python",
                "-c",
                (
                    "import json; from pathlib import Path; "
                    "nb=json.loads(Path('notebooks/experiment.ipynb').read_text(encoding='utf-8')); "
                    "assert nb.get('nbformat')==4; print('notebook format ready')"
                ),
            ],
            "notebook format ready",
        ),
        _command_gate(
            "notebook-execute",
            "notebook code cells execute in-process",
            [
                executable,
                "--offline",
                "run",
                "python",
                "-c",
                f"from {package_name}.execute import execute_notebook; evidence=execute_notebook(); print(evidence['status'])",
            ],
            "executed",
        ),
        _command_gate(
            "unit-tests",
            "local unit tests",
            [executable, "--offline", "run", "python", "-m", "unittest", "discover", "-s", "tests", "-v"],
        ),
        GateSpec(
            "provenance-files",
            "experiment parameters and data provenance files",
            "artifact",
            artifact_patterns=("params.json", "data/SOURCES.md", "data/sample.csv", "notebooks/experiment.ipynb"),
            min_artifacts=4,
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
        ClaimSpec("notebook-format-valid", "The generated file is an nbformat 4 notebook.", "local generated scaffold", ("notebook-format",)),
        ClaimSpec("notebook-executes", "Notebook code cells run and produce a RESULT mapping.", "local generated scaffold", ("notebook-execute", "unit-tests")),
        ClaimSpec("parameters-preserved", "Experiment parameters are stored next to the notebook.", "local generated scaffold", ("provenance-files", "unit-tests")),
        ClaimSpec("data-provenance-preserved", "Input data origins are recorded in data/SOURCES.md.", "local generated scaffold", ("provenance-files", "unit-tests")),
        ClaimSpec(
            "jupyter-lab-runtime",
            "The notebook runs inside an interactive JupyterLab or Jupyter kernel session.",
            "external Jupyter runtime",
            (),
            True,
            "This suite executes code cells in-process. JupyterLab / ipykernel is not a verification gate.",
        ),
    )
    return VerificationSuite(
        "python-notebook",
        "0.1",
        "generated reproducible Python notebook scaffold",
        gates,
        claims,
        "python",
        (
            "Public dataset publication and experiment trackers are outside this verification scope.",
            "JupyterLab and ipykernel are development tools, not VERIFIED gates.",
            "This is a notebook + provenance profile, not a trained-model serving line.",
        ),
    )
