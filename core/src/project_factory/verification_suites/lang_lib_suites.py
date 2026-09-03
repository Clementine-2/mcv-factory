"""Auto-generated E1 language-root verification suites (cli)."""
from __future__ import annotations

from ..verification import ClaimSpec, GateSpec, ProviderView, VerificationSuite, _command_gate

def build_go_lib_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "go-lib-build",
            "generated go lib build",
            [executable, 'go', 'build', './...'],
        ),
        _command_gate(
            "go-lib-test",
            "generated go lib tests",
            [executable, 'go', 'test', './...'],
        ),
        GateSpec(
            "go-lib-artifacts",
            "compiled lib artifacts",
            "artifact",
            artifact_patterns=('go.sum',),
            min_artifacts=1,
        )
    )
    claims = (
        ClaimSpec("go-lib-builds", "The generated go lib builds locally.", "local generated scaffold", ("go-lib-build",)),
        ClaimSpec("go-lib-tests", "The generated go lib tests pass locally.", "local generated scaffold", ("go-lib-test",)),
        ClaimSpec(
            "go-lib-publish",
            "The go lib is published to its registry.",
            "public registry publication",
            (),
            True,
            "Registry publication is outside this verification scope.",
        )
    )
    return VerificationSuite(
        "go-lib",
        "0.1",
        "generated go lib scaffold",
        gates,
        claims,
        "go",
        (
            "Public registry publication is outside this verification scope.",
            "Toolchain must be installed locally; without it generation/verification fail at runtime (not at selection).",
        ),
    )

def build_java_lib_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "java-lib-build",
            "generated java lib build",
            [executable, 'gradle', 'build', '--offline'],
        ),
        _command_gate(
            "java-lib-test",
            "generated java lib tests",
            [executable, 'gradle', 'test', '--offline'],
        ),
        GateSpec(
            "java-lib-artifacts",
            "compiled lib artifacts",
            "artifact",
            artifact_patterns=('build/libs/*.jar',),
            min_artifacts=1,
        )
    )
    claims = (
        ClaimSpec("java-lib-builds", "The generated java lib builds locally.", "local generated scaffold", ("java-lib-build",)),
        ClaimSpec("java-lib-tests", "The generated java lib tests pass locally.", "local generated scaffold", ("java-lib-test",)),
        ClaimSpec(
            "java-lib-publish",
            "The java lib is published to its registry.",
            "public registry publication",
            (),
            True,
            "Registry publication is outside this verification scope.",
        )
    )
    return VerificationSuite(
        "java-lib",
        "0.1",
        "generated java lib scaffold",
        gates,
        claims,
        "java",
        (
            "Public registry publication is outside this verification scope.",
            "Toolchain must be installed locally; without it generation/verification fail at runtime (not at selection).",
        ),
    )

def build_kotlin_lib_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "kotlin-lib-build",
            "generated kotlin lib build",
            [executable, 'gradle', 'build', '--offline'],
        ),
        _command_gate(
            "kotlin-lib-test",
            "generated kotlin lib tests",
            [executable, 'gradle', 'test', '--offline'],
        ),
        GateSpec(
            "kotlin-lib-artifacts",
            "compiled lib artifacts",
            "artifact",
            artifact_patterns=('build/libs/*.jar',),
            min_artifacts=1,
        )
    )
    claims = (
        ClaimSpec("kotlin-lib-builds", "The generated kotlin lib builds locally.", "local generated scaffold", ("kotlin-lib-build",)),
        ClaimSpec("kotlin-lib-tests", "The generated kotlin lib tests pass locally.", "local generated scaffold", ("kotlin-lib-test",)),
        ClaimSpec(
            "kotlin-lib-publish",
            "The kotlin lib is published to its registry.",
            "public registry publication",
            (),
            True,
            "Registry publication is outside this verification scope.",
        )
    )
    return VerificationSuite(
        "kotlin-lib",
        "0.1",
        "generated kotlin lib scaffold",
        gates,
        claims,
        "kotlin",
        (
            "Public registry publication is outside this verification scope.",
            "Toolchain must be installed locally; without it generation/verification fail at runtime (not at selection).",
        ),
    )

def build_dart_lib_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "dart-lib-build",
            "generated dart lib build",
            [executable, 'dart', 'analyze'],
        ),
        _command_gate(
            "dart-lib-test",
            "generated dart lib tests",
            [executable, 'dart', 'test'],
        ),
        GateSpec(
            "dart-lib-artifacts",
            "compiled lib artifacts",
            "artifact",
            artifact_patterns=('pubspec.lock',),
            min_artifacts=1,
        )
    )
    claims = (
        ClaimSpec("dart-lib-builds", "The generated dart lib builds locally.", "local generated scaffold", ("dart-lib-build",)),
        ClaimSpec("dart-lib-tests", "The generated dart lib tests pass locally.", "local generated scaffold", ("dart-lib-test",)),
        ClaimSpec(
            "dart-lib-publish",
            "The dart lib is published to its registry.",
            "public registry publication",
            (),
            True,
            "Registry publication is outside this verification scope.",
        )
    )
    return VerificationSuite(
        "dart-lib",
        "0.1",
        "generated dart lib scaffold",
        gates,
        claims,
        "dart",
        (
            "Public registry publication is outside this verification scope.",
            "Toolchain must be installed locally; without it generation/verification fail at runtime (not at selection).",
        ),
    )

def build_swift_lib_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "swift-lib-build",
            "generated swift lib build",
            [executable, 'swift', 'build'],
        ),
        _command_gate(
            "swift-lib-test",
            "generated swift lib tests",
            [executable, 'swift', 'test'],
        ),
        GateSpec(
            "swift-lib-artifacts",
            "compiled lib artifacts",
            "artifact",
            artifact_patterns=('.build/debug/*',),
            min_artifacts=1,
        )
    )
    claims = (
        ClaimSpec("swift-lib-builds", "The generated swift lib builds locally.", "local generated scaffold", ("swift-lib-build",)),
        ClaimSpec("swift-lib-tests", "The generated swift lib tests pass locally.", "local generated scaffold", ("swift-lib-test",)),
        ClaimSpec(
            "swift-lib-publish",
            "The swift lib is published to its registry.",
            "public registry publication",
            (),
            True,
            "Registry publication is outside this verification scope.",
        )
    )
    return VerificationSuite(
        "swift-lib",
        "0.1",
        "generated swift lib scaffold",
        gates,
        claims,
        "swift",
        (
            "Public registry publication is outside this verification scope.",
            "Toolchain must be installed locally; without it generation/verification fail at runtime (not at selection).",
        ),
    )

def build_cpp_lib_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "cpp-lib-build",
            "generated cpp lib build",
            [executable, 'cmake', '--build', 'build'],
        ),
        _command_gate(
            "cpp-lib-test",
            "generated cpp lib tests",
            [executable, 'ctest', '--test-dir', 'build'],
        ),
        GateSpec(
            "cpp-lib-artifacts",
            "compiled lib artifacts",
            "artifact",
            artifact_patterns=('build/*',),
            min_artifacts=1,
        )
    )
    claims = (
        ClaimSpec("cpp-lib-builds", "The generated cpp lib builds locally.", "local generated scaffold", ("cpp-lib-build",)),
        ClaimSpec("cpp-lib-tests", "The generated cpp lib tests pass locally.", "local generated scaffold", ("cpp-lib-test",)),
        ClaimSpec(
            "cpp-lib-publish",
            "The cpp lib is published to its registry.",
            "public registry publication",
            (),
            True,
            "Registry publication is outside this verification scope.",
        )
    )
    return VerificationSuite(
        "cpp-lib",
        "0.1",
        "generated cpp lib scaffold",
        gates,
        claims,
        "cpp",
        (
            "Public registry publication is outside this verification scope.",
            "Toolchain must be installed locally; without it generation/verification fail at runtime (not at selection).",
        ),
    )

def build_c_lib_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "c-lib-build",
            "generated c lib build",
            [executable, 'gcc', '-c', '-o', 'build/lib.o', 'src/lib.c'],
        ),
        GateSpec(
            "c-lib-artifacts",
            "compiled lib artifacts",
            "artifact",
            artifact_patterns=('build/lib.o',),
            min_artifacts=1,
        )
    )
    claims = (
        ClaimSpec("c-lib-builds", "The generated c lib builds locally.", "local generated scaffold", ("c-lib-build",)),
        ClaimSpec(
            "c-lib-publish",
            "The c lib is published to its registry.",
            "public registry publication",
            (),
            True,
            "Registry publication is outside this verification scope.",
        )
    )
    return VerificationSuite(
        "c-lib",
        "0.1",
        "generated c lib scaffold",
        gates,
        claims,
        "c",
        (
            "Public registry publication is outside this verification scope.",
            "Toolchain must be installed locally; without it generation/verification fail at runtime (not at selection).",
        ),
    )

def build_php_lib_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "php-lib-build",
            "generated php lib build",
            [executable, 'php', '-l', 'src/__PKG__.php'],
        ),
        GateSpec(
            "php-lib-artifacts",
            "compiled lib artifacts",
            "artifact",
            artifact_patterns=('composer.lock',),
            min_artifacts=1,
        )
    )
    claims = (
        ClaimSpec("php-lib-builds", "The generated php lib builds locally.", "local generated scaffold", ("php-lib-build",)),
        ClaimSpec(
            "php-lib-publish",
            "The php lib is published to its registry.",
            "public registry publication",
            (),
            True,
            "Registry publication is outside this verification scope.",
        )
    )
    return VerificationSuite(
        "php-lib",
        "0.1",
        "generated php lib scaffold",
        gates,
        claims,
        "php",
        (
            "Public registry publication is outside this verification scope.",
            "Toolchain must be installed locally; without it generation/verification fail at runtime (not at selection).",
        ),
    )

def build_r_lib_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "r-lib-build",
            "generated r lib build",
            [executable, 'Rscript', '-e', 'invisible(scaffold_status())'],
        ),
        _command_gate(
            "r-lib-test",
            "generated r lib tests",
            [executable, 'Rscript', '-e', 'stopifnot(scaffold_status() == "__PKG__ library scaffold ready")'],
        ),
        GateSpec(
            "r-lib-artifacts",
            "compiled lib artifacts",
            "artifact",
            artifact_patterns=('DESCRIPTION',),
            min_artifacts=1,
        )
    )
    claims = (
        ClaimSpec("r-lib-builds", "The generated r lib builds locally.", "local generated scaffold", ("r-lib-build",)),
        ClaimSpec("r-lib-tests", "The generated r lib tests pass locally.", "local generated scaffold", ("r-lib-test",)),
        ClaimSpec(
            "r-lib-publish",
            "The r lib is published to its registry.",
            "public registry publication",
            (),
            True,
            "Registry publication is outside this verification scope.",
        )
    )
    return VerificationSuite(
        "r-lib",
        "0.1",
        "generated r lib scaffold",
        gates,
        claims,
        "r",
        (
            "Public registry publication is outside this verification scope.",
            "Toolchain must be installed locally; without it generation/verification fail at runtime (not at selection).",
        ),
    )
