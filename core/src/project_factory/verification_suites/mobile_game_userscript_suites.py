"""Auto-generated E3 mobile-app / game / userscript verification suites."""
from __future__ import annotations

from ..verification import ClaimSpec, GateSpec, ProviderView, VerificationSuite, _command_gate

def build_flutter_mobile_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "flutter-mobile-build",
            "generated flutter-mobile build",
            [executable, 'flutter', 'analyze'],
        ),
    )
    claims = (
        ClaimSpec("flutter-mobile-builds", "The generated flutter-mobile builds locally.", "local generated scaffold", ("flutter-mobile-build",)),
    )
    return VerificationSuite(
        "flutter-mobile",
        "0.1",
        "generated flutter-mobile scaffold",
        gates,
        claims,
        "dart",
        (
            "Toolchain must be installed locally; without it generation/verification fail at runtime (not at selection).",
        ),
    )

def build_kotlin_mobile_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "kotlin-mobile-build",
            "generated kotlin-mobile build",
            [executable, 'gradle', 'assembleDebug', '--offline'],
        ),
    )
    claims = (
        ClaimSpec("kotlin-mobile-builds", "The generated kotlin-mobile builds locally.", "local generated scaffold", ("kotlin-mobile-build",)),
    )
    return VerificationSuite(
        "kotlin-mobile",
        "0.1",
        "generated kotlin-mobile scaffold",
        gates,
        claims,
        "kotlin",
        (
            "Toolchain must be installed locally; without it generation/verification fail at runtime (not at selection).",
        ),
    )

def build_swift_mobile_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "swift-mobile-build",
            "generated swift-mobile build",
            [executable, 'swift', 'build'],
        ),
        _command_gate(
            "swift-mobile-test",
            "generated swift-mobile tests",
            [executable, 'swift', 'test'],
        ),
    )
    claims = (
        ClaimSpec("swift-mobile-builds", "The generated swift-mobile builds locally.", "local generated scaffold", ("swift-mobile-build",)),
        ClaimSpec("swift-mobile-tests", "The generated swift-mobile tests pass locally.", "local generated scaffold", ("swift-mobile-test",)),
    )
    return VerificationSuite(
        "swift-mobile",
        "0.1",
        "generated swift-mobile scaffold",
        gates,
        claims,
        "swift",
        (
            "Toolchain must be installed locally; without it generation/verification fail at runtime (not at selection).",
        ),
    )

def build_bevy_game_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "bevy-game-build",
            "generated bevy-game build",
            [executable, 'cargo', 'build', '--offline'],
        ),
        _command_gate(
            "bevy-game-test",
            "generated bevy-game tests",
            [executable, 'cargo', 'test', '--offline'],
        ),
    )
    claims = (
        ClaimSpec("bevy-game-builds", "The generated bevy-game builds locally.", "local generated scaffold", ("bevy-game-build",)),
        ClaimSpec("bevy-game-tests", "The generated bevy-game tests pass locally.", "local generated scaffold", ("bevy-game-test",)),
    )
    return VerificationSuite(
        "bevy-game",
        "0.1",
        "generated bevy-game scaffold",
        gates,
        claims,
        "rust",
        (
            "Toolchain must be installed locally; without it generation/verification fail at runtime (not at selection).",
        ),
    )

def build_godot_game_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "godot-game-build",
            "generated godot-game build",
            [executable, 'godot', '--headless', '--quit'],
        ),
    )
    claims = (
        ClaimSpec("godot-game-builds", "The generated godot-game builds locally.", "local generated scaffold", ("godot-game-build",)),
    )
    return VerificationSuite(
        "godot-game",
        "0.1",
        "generated godot-game scaffold",
        gates,
        claims,
        "gdscript",
        (
            "Toolchain must be installed locally; without it generation/verification fail at runtime (not at selection).",
        ),
    )

def build_typescript_userscript_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "typescript-userscript-build",
            "generated typescript-userscript build",
            [executable, 'npm', 'run', 'build'],
        ),
    )
    claims = (
        ClaimSpec("typescript-userscript-builds", "The generated typescript-userscript builds locally.", "local generated scaffold", ("typescript-userscript-build",)),
    )
    return VerificationSuite(
        "typescript-userscript",
        "0.1",
        "generated typescript-userscript scaffold",
        gates,
        claims,
        "node",
        (
            "Toolchain must be installed locally; without it generation/verification fail at runtime (not at selection).",
        ),
    )
