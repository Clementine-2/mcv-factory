from __future__ import annotations

from ..verification import ClaimSpec, GateSpec, ProviderView, VerificationSuite, _command_gate


def build_python_native_extension_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate("crate-tests", "generated PyO3 unit tests", [executable, "test"]),
        _command_gate("maturin-build", "maturin wheel build", ["maturin", "build"]),
        GateSpec(
            "wheel-artifacts",
            "maturin wheel artifacts",
            "artifact",
            artifact_patterns=("target/wheels/*.whl", "dist/*.whl"),
            min_artifacts=1,
        ),
    )
    claims = (
        ClaimSpec("crate-tests-pass", "The generated PyO3 crate tests pass locally.", "local generated scaffold", ("crate-tests",)),
        ClaimSpec("wheel-builds", "maturin produces a wheel locally.", "local package build", ("maturin-build", "wheel-artifacts")),
        ClaimSpec(
            "python-import",
            "The built extension imports in a Python interpreter.",
            "installed native module",
            (),
            True,
            "This suite does not pip-install the wheel.",
        ),
    )
    return VerificationSuite(
        "python-native-extension",
        "0.1",
        "generated maturin/PyO3 native extension scaffold",
        gates,
        claims,
        "rust",
        (
            "Supported maturin is 1.8.3; newer observed versions are not auto-promoted.",
            "The wheel is not installed into a Python environment by this suite.",
        ),
    )
