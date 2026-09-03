from __future__ import annotations

from ..verification import (
    ClaimSpec,
    GateSpec,
    ProviderView,
    VerificationSuite,
    _command_gate,
)


def build_rust_library_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "crate-tests",
            "generated Rust unit tests",
            [executable, "test", "--offline"],
            "test result: ok",
        ),
        _command_gate(
            "crate-build",
            "generated Rust library build",
            [executable, "build", "--offline"],
            "Finished",
        ),
        GateSpec(
            "crate-artifacts",
            "compiled library artifacts",
            "artifact",
            artifact_patterns=("target/debug/*.rlib", "target/debug/*.lib", "target/debug/lib*.rlib"),
            min_artifacts=1,
        ),
    )
    claims = (
        ClaimSpec("crate-tests-pass", "The generated Rust library unit tests pass locally.", "local generated scaffold", ("crate-tests",)),
        ClaimSpec("crate-builds", "The generated crate compiles a library artifact locally.", "local generated scaffold", ("crate-build", "crate-artifacts")),
        ClaimSpec(
            "crates-io-publish",
            "The crate is published to crates.io.",
            "public registry publication",
            (),
            True,
            "crates.io publication is outside this verification scope.",
        ),
    )
    return VerificationSuite(
        "rust-library",
        "0.1",
        "generated Rust library crate scaffold",
        gates,
        claims,
        "rust",
        (
            "Public crates.io publication is outside this verification scope.",
            "This profile is a Cargo library, not a Maturin/PyO3 extension.",
            "Maturin remains observed until a native-extension line is owned.",
        ),
    )
