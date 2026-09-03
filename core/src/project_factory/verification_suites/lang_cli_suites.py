"""Auto-generated E1 language-root verification suites (cli)."""
from __future__ import annotations

from ..verification import ClaimSpec, GateSpec, ProviderView, VerificationSuite, _command_gate

def build_go_cli_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "go-cli-build",
            "generated go cli build",
            [executable, 'go', 'build', './...'],
        ),
        _command_gate(
            "go-cli-test",
            "generated go cli tests",
            [executable, 'go', 'test', './...'],
        ),
        GateSpec(
            "go-cli-artifacts",
            "compiled cli artifacts",
            "artifact",
            artifact_patterns=('go.sum',),
            min_artifacts=1,
        )
    )
    claims = (
        ClaimSpec("go-cli-builds", "The generated go cli builds locally.", "local generated scaffold", ("go-cli-build",)),
        ClaimSpec("go-cli-tests", "The generated go cli tests pass locally.", "local generated scaffold", ("go-cli-test",)),
        ClaimSpec(
            "go-cli-publish",
            "The go cli is published to its registry.",
            "public registry publication",
            (),
            True,
            "Registry publication is outside this verification scope.",
        )
    )
    return VerificationSuite(
        "go-cli",
        "0.1",
        "generated go cli scaffold",
        gates,
        claims,
        "go",
        (
            "Public registry publication is outside this verification scope.",
            "Toolchain must be installed locally; without it generation/verification fail at runtime (not at selection).",
        ),
    )

def build_java_cli_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "java-cli-build",
            "generated java cli build",
            [executable, 'gradle', 'build', '--offline'],
        ),
        _command_gate(
            "java-cli-test",
            "generated java cli tests",
            [executable, 'gradle', 'test', '--offline'],
        ),
        GateSpec(
            "java-cli-artifacts",
            "compiled cli artifacts",
            "artifact",
            artifact_patterns=('build/libs/*.jar',),
            min_artifacts=1,
        )
    )
    claims = (
        ClaimSpec("java-cli-builds", "The generated java cli builds locally.", "local generated scaffold", ("java-cli-build",)),
        ClaimSpec("java-cli-tests", "The generated java cli tests pass locally.", "local generated scaffold", ("java-cli-test",)),
        ClaimSpec(
            "java-cli-publish",
            "The java cli is published to its registry.",
            "public registry publication",
            (),
            True,
            "Registry publication is outside this verification scope.",
        )
    )
    return VerificationSuite(
        "java-cli",
        "0.1",
        "generated java cli scaffold",
        gates,
        claims,
        "java",
        (
            "Public registry publication is outside this verification scope.",
            "Toolchain must be installed locally; without it generation/verification fail at runtime (not at selection).",
        ),
    )

def build_kotlin_cli_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "kotlin-cli-build",
            "generated kotlin cli build",
            [executable, 'gradle', 'build', '--offline'],
        ),
        _command_gate(
            "kotlin-cli-test",
            "generated kotlin cli tests",
            [executable, 'gradle', 'test', '--offline'],
        ),
        GateSpec(
            "kotlin-cli-artifacts",
            "compiled cli artifacts",
            "artifact",
            artifact_patterns=('build/libs/*.jar',),
            min_artifacts=1,
        )
    )
    claims = (
        ClaimSpec("kotlin-cli-builds", "The generated kotlin cli builds locally.", "local generated scaffold", ("kotlin-cli-build",)),
        ClaimSpec("kotlin-cli-tests", "The generated kotlin cli tests pass locally.", "local generated scaffold", ("kotlin-cli-test",)),
        ClaimSpec(
            "kotlin-cli-publish",
            "The kotlin cli is published to its registry.",
            "public registry publication",
            (),
            True,
            "Registry publication is outside this verification scope.",
        )
    )
    return VerificationSuite(
        "kotlin-cli",
        "0.1",
        "generated kotlin cli scaffold",
        gates,
        claims,
        "kotlin",
        (
            "Public registry publication is outside this verification scope.",
            "Toolchain must be installed locally; without it generation/verification fail at runtime (not at selection).",
        ),
    )

def build_dart_cli_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "dart-cli-build",
            "generated dart cli build",
            [executable, 'dart', 'analyze'],
        ),
        _command_gate(
            "dart-cli-test",
            "generated dart cli tests",
            [executable, 'dart', 'test'],
        ),
        GateSpec(
            "dart-cli-artifacts",
            "compiled cli artifacts",
            "artifact",
            artifact_patterns=('pubspec.lock',),
            min_artifacts=1,
        )
    )
    claims = (
        ClaimSpec("dart-cli-builds", "The generated dart cli builds locally.", "local generated scaffold", ("dart-cli-build",)),
        ClaimSpec("dart-cli-tests", "The generated dart cli tests pass locally.", "local generated scaffold", ("dart-cli-test",)),
        ClaimSpec(
            "dart-cli-publish",
            "The dart cli is published to its registry.",
            "public registry publication",
            (),
            True,
            "Registry publication is outside this verification scope.",
        )
    )
    return VerificationSuite(
        "dart-cli",
        "0.1",
        "generated dart cli scaffold",
        gates,
        claims,
        "dart",
        (
            "Public registry publication is outside this verification scope.",
            "Toolchain must be installed locally; without it generation/verification fail at runtime (not at selection).",
        ),
    )

def build_swift_cli_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "swift-cli-build",
            "generated swift cli build",
            [executable, 'swift', 'build'],
        ),
        _command_gate(
            "swift-cli-test",
            "generated swift cli tests",
            [executable, 'swift', 'test'],
        ),
        GateSpec(
            "swift-cli-artifacts",
            "compiled cli artifacts",
            "artifact",
            artifact_patterns=('.build/debug/*',),
            min_artifacts=1,
        )
    )
    claims = (
        ClaimSpec("swift-cli-builds", "The generated swift cli builds locally.", "local generated scaffold", ("swift-cli-build",)),
        ClaimSpec("swift-cli-tests", "The generated swift cli tests pass locally.", "local generated scaffold", ("swift-cli-test",)),
        ClaimSpec(
            "swift-cli-publish",
            "The swift cli is published to its registry.",
            "public registry publication",
            (),
            True,
            "Registry publication is outside this verification scope.",
        )
    )
    return VerificationSuite(
        "swift-cli",
        "0.1",
        "generated swift cli scaffold",
        gates,
        claims,
        "swift",
        (
            "Public registry publication is outside this verification scope.",
            "Toolchain must be installed locally; without it generation/verification fail at runtime (not at selection).",
        ),
    )

def build_cpp_cli_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "cpp-cli-build",
            "generated cpp cli build",
            [executable, 'cmake', '--build', 'build'],
        ),
        _command_gate(
            "cpp-cli-test",
            "generated cpp cli tests",
            [executable, 'ctest', '--test-dir', 'build'],
        ),
        GateSpec(
            "cpp-cli-artifacts",
            "compiled cli artifacts",
            "artifact",
            artifact_patterns=('build/*',),
            min_artifacts=1,
        )
    )
    claims = (
        ClaimSpec("cpp-cli-builds", "The generated cpp cli builds locally.", "local generated scaffold", ("cpp-cli-build",)),
        ClaimSpec("cpp-cli-tests", "The generated cpp cli tests pass locally.", "local generated scaffold", ("cpp-cli-test",)),
        ClaimSpec(
            "cpp-cli-publish",
            "The cpp cli is published to its registry.",
            "public registry publication",
            (),
            True,
            "Registry publication is outside this verification scope.",
        )
    )
    return VerificationSuite(
        "cpp-cli",
        "0.1",
        "generated cpp cli scaffold",
        gates,
        claims,
        "cpp",
        (
            "Public registry publication is outside this verification scope.",
            "Toolchain must be installed locally; without it generation/verification fail at runtime (not at selection).",
        ),
    )

def build_c_cli_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "c-cli-build",
            "generated c cli build",
            [executable, 'gcc', '-o', 'build/app', 'src/main.c'],
        ),
        GateSpec(
            "c-cli-artifacts",
            "compiled cli artifacts",
            "artifact",
            artifact_patterns=('build/app',),
            min_artifacts=1,
        )
    )
    claims = (
        ClaimSpec("c-cli-builds", "The generated c cli builds locally.", "local generated scaffold", ("c-cli-build",)),
        ClaimSpec(
            "c-cli-publish",
            "The c cli is published to its registry.",
            "public registry publication",
            (),
            True,
            "Registry publication is outside this verification scope.",
        )
    )
    return VerificationSuite(
        "c-cli",
        "0.1",
        "generated c cli scaffold",
        gates,
        claims,
        "c",
        (
            "Public registry publication is outside this verification scope.",
            "Toolchain must be installed locally; without it generation/verification fail at runtime (not at selection).",
        ),
    )

def build_php_cli_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "php-cli-build",
            "generated php cli build",
            [executable, 'php', '-l', 'bin/__PKG__.php'],
        ),
        GateSpec(
            "php-cli-artifacts",
            "compiled cli artifacts",
            "artifact",
            artifact_patterns=('composer.lock',),
            min_artifacts=1,
        )
    )
    claims = (
        ClaimSpec("php-cli-builds", "The generated php cli builds locally.", "local generated scaffold", ("php-cli-build",)),
        ClaimSpec(
            "php-cli-publish",
            "The php cli is published to its registry.",
            "public registry publication",
            (),
            True,
            "Registry publication is outside this verification scope.",
        )
    )
    return VerificationSuite(
        "php-cli",
        "0.1",
        "generated php cli scaffold",
        gates,
        claims,
        "php",
        (
            "Public registry publication is outside this verification scope.",
            "Toolchain must be installed locally; without it generation/verification fail at runtime (not at selection).",
        ),
    )

def build_r_cli_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "r-cli-build",
            "generated r cli build",
            [executable, 'Rscript', '-e', 'invisible(scaffold_status())'],
        ),
        _command_gate(
            "r-cli-test",
            "generated r cli tests",
            [executable, 'Rscript', '-e', 'stopifnot(scaffold_status() == "__PKG__ scaffold ready")'],
        ),
        GateSpec(
            "r-cli-artifacts",
            "compiled cli artifacts",
            "artifact",
            artifact_patterns=('DESCRIPTION',),
            min_artifacts=1,
        )
    )
    claims = (
        ClaimSpec("r-cli-builds", "The generated r cli builds locally.", "local generated scaffold", ("r-cli-build",)),
        ClaimSpec("r-cli-tests", "The generated r cli tests pass locally.", "local generated scaffold", ("r-cli-test",)),
        ClaimSpec(
            "r-cli-publish",
            "The r cli is published to its registry.",
            "public registry publication",
            (),
            True,
            "Registry publication is outside this verification scope.",
        )
    )
    return VerificationSuite(
        "r-cli",
        "0.1",
        "generated r cli scaffold",
        gates,
        claims,
        "r",
        (
            "Public registry publication is outside this verification scope.",
            "Toolchain must be installed locally; without it generation/verification fail at runtime (not at selection).",
        ),
    )
