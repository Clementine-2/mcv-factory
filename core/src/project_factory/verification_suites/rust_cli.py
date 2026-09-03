from __future__ import annotations

from ..verification import ClaimSpec, GateSpec, ProviderView, VerificationSuite, _command_gate


def build_rust_cli_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "crate-tests",
            "generated Rust CLI unit tests",
            [executable, "test", "--offline"],
            "test result: ok",
        ),
        _command_gate(
            "crate-build",
            "generated Rust CLI build",
            [executable, "build", "--offline"],
            "Finished",
        ),
        GateSpec(
            "crate-artifacts",
            "compiled CLI artifacts",
            "artifact",
            artifact_patterns=(
                "target/debug/*.rlib",
                "target/debug/*.lib",
                "target/debug/*.exe",
                "target/debug/lib*.rlib",
            ),
            min_artifacts=1,
        ),
    )
    claims = (
        ClaimSpec("crate-tests-pass", "The generated Rust CLI unit tests pass locally.", "local generated scaffold", ("crate-tests",)),
        ClaimSpec("crate-builds", "The generated clap CLI compiles locally.", "local generated scaffold", ("crate-build", "crate-artifacts")),
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
        "rust-cli",
        "0.1",
        "generated Rust clap CLI scaffold",
        gates,
        claims,
        "rust",
        (
            "Public crates.io publication is outside this verification scope.",
            "This profile is a clap CLI on the Cargo language root, not the Python argparse/Typer lines.",
            "clap color is disabled so this Windows GNU host does not compile windows-sys (dlltool missing).",
        ),
    )
