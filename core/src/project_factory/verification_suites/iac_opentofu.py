from __future__ import annotations

from ..verification import (
    ClaimSpec,
    GateSpec,
    ProviderView,
    VerificationSuite,
    _command_gate,
)


def build_iac_opentofu_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "tf-syntax",
            "opentofu drawing syntax check",
            [executable, "--offline", "run", "python", "-m", "unittest", "discover", "-s", "tests", "-v"],
        ),
        GateSpec(
            "tf-artifacts",
            "main.tf, variables.tf, outputs.tf",
            "artifact",
            artifact_patterns=("main.tf", "variables.tf", "outputs.tf"),
            min_artifacts=3,
        ),
    )
    claims = (
        ClaimSpec("tf-drawing", "main.tf declares null_resource scaffold.", "local drawing", ("tf-syntax", "tf-artifacts")),
        ClaimSpec(
            "tofu-runtime",
            "tofu plan/apply ran against live infra.",
            "tofu CLI",
            (),
            True,
            "No tofu CLI is installed. The factory does not install OpenTofu.",
        ),
    )
    return VerificationSuite(
        "iac-opentofu",
        "0.1",
        "opentofu drawing (no CLI)",
        gates,
        claims,
        "python",
        ("main.tf is the local drawing. `tofu plan` remains unverified.",),
    )
