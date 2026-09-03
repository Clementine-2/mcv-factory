from __future__ import annotations

from ..verification import (
    ClaimSpec,
    GateSpec,
    ProviderView,
    VerificationSuite,
    _command_gate,
    _python_package_name,
)


def build_python_model_serving_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    package_name = _python_package_name(project_name)
    executable = provider.executable
    gates = (
        _command_gate(
            "serve-imports",
            "generated model-serving import",
            [
                executable,
                "--offline",
                "run",
                "python",
                "-c",
                f"from {package_name}.serve import scaffold_status; print(scaffold_status())",
            ],
            "model serving scaffold ready",
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
        ClaimSpec("serve-importable", "The generated serving module imports locally.", "local generated scaffold", ("serve-imports",)),
        ClaimSpec("predict-ok", "predict() returns a score in-process.", "local generated scaffold", ("unit-tests",)),
        ClaimSpec("package-builds", "The generated scaffold builds a wheel and source distribution locally.", "local package build", ("package-build", "package-artifacts")),
        ClaimSpec(
            "gpu-runtime",
            "A GPU model was loaded and served.",
            "external model runtime",
            (),
            True,
            "No weights were downloaded and no GPU was used.",
        ),
    )
    return VerificationSuite(
        "python-model-serving",
        "0.1",
        "generated model-serving stub scaffold",
        gates,
        claims,
        "python",
        ("This is a stub scorer. Torch/ONNX serving remains unverified.",),
    )
