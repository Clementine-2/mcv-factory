from __future__ import annotations

from ..verification import (
    ClaimSpec,
    GateSpec,
    ProviderView,
    VerificationSuite,
    _command_gate,
    _python_package_name,
)


def build_python_lambda_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    package_name = _python_package_name(project_name)
    executable = provider.executable
    gates = (
        _command_gate(
            "handler-imports",
            "generated Lambda handler import",
            [
                executable,
                "--offline",
                "run",
                "python",
                "-c",
                f"from {package_name}.handler import handler; print(handler({{}}, None)['body'])",
            ],
            "lambda scaffold ready",
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
        ClaimSpec("handler-importable", "The generated Lambda handler imports locally.", "local generated scaffold", ("handler-imports",)),
        ClaimSpec("handler-ok", "The handler returns HTTP 200 in-process.", "local generated scaffold", ("unit-tests",)),
        ClaimSpec("package-builds", "The generated scaffold builds a wheel and source distribution locally.", "local package build", ("package-build", "package-artifacts")),
        ClaimSpec(
            "aws-runtime",
            "The function ran on AWS Lambda.",
            "AWS Lambda runtime",
            (),
            True,
            "AWS deploy and invoke were not launched by this suite.",
        ),
    )
    return VerificationSuite(
        "python-lambda",
        "0.1",
        "generated AWS Lambda handler scaffold",
        gates,
        claims,
        "python",
        (
            "AWS account, IAM, and live invoke are outside this verification scope.",
            "The factory does not install the AWS CLI, SAM, or CDK.",
        ),
    )
