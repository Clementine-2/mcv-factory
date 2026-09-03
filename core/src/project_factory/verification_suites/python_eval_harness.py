from __future__ import annotations

from ..verification import (
    ClaimSpec,
    GateSpec,
    ProviderView,
    VerificationSuite,
    _command_gate,
    _python_package_name,
)


def build_python_eval_harness_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    package_name = _python_package_name(project_name)
    executable = provider.executable
    gates = (
        _command_gate(
            "harness-imports",
            "generated eval harness import",
            [
                executable,
                "--offline",
                "run",
                "python",
                "-c",
                f"from {package_name}.harness import scaffold_status; print(scaffold_status())",
            ],
            "eval harness scaffold ready",
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
        ClaimSpec("harness-importable", "The generated eval harness imports locally.", "local generated scaffold", ("harness-imports",)),
        ClaimSpec("fixture-scores", "The harness scores the local gold/pred fixtures.", "local generated scaffold", ("unit-tests",)),
        ClaimSpec("package-builds", "The generated scaffold builds a wheel and source distribution locally.", "local package build", ("package-build", "package-artifacts")),
        ClaimSpec(
            "model-runtime",
            "A live model was trained or downloaded and evaluated.",
            "external model runtime",
            (),
            True,
            "No model weights were downloaded or trained by this suite.",
        ),
    )
    return VerificationSuite(
        "python-eval-harness",
        "0.1",
        "generated Python evaluation harness scaffold",
        gates,
        claims,
        "python",
        (
            "This scores frozen fixtures. Training and leaderboards are outside this verification scope.",
        ),
    )
