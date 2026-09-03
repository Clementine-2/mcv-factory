from __future__ import annotations

from ..verification import ClaimSpec, GateSpec, ProviderView, VerificationSuite, _command_gate


def build_typescript_library_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "npm-ci-offline",
            "offline npm install from lockfile",
            [executable, "ci", "--offline", "--no-fund", "--no-audit"],
        ),
        _command_gate("unit-tests", "local TypeScript library tests", [executable, "test"]),
        _command_gate("package-pack", "local npm package creation", [executable, "pack", "--ignore-scripts"]),
        GateSpec("package-artifact", "npm tarball artifact", "artifact", artifact_patterns=("*.tgz",), min_artifacts=1),
        GateSpec(
            "library-artifacts",
            "compiled TypeScript library artifacts",
            "artifact",
            artifact_patterns=("dist/index.js", "dist/index.d.ts"),
            min_artifacts=2,
        ),
    )
    claims = (
        ClaimSpec("tests-pass", "The generated TypeScript library tests pass locally.", "local generated scaffold", ("unit-tests",)),
        ClaimSpec("package-created", "The generated scaffold can be packed as an npm tarball locally.", "local package build", ("package-pack", "package-artifact")),
        ClaimSpec("library-builds", "TypeScript compiles a library artifact locally.", "local package build", ("library-artifacts",)),
    )
    return VerificationSuite(
        "typescript-library",
        "0.1",
        "generated TypeScript library scaffold",
        gates,
        claims,
        "node",
        (
            "Public npm publication is outside this verification scope.",
            "This profile is a TypeScript library, not a Vite web UI.",
        ),
    )
