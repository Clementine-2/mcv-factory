from __future__ import annotations

from ..verification import (
    ClaimSpec,
    GateSpec,
    ProviderView,
    VerificationSuite,
    _command_gate,
    _python_package_name,
)


def build_python_bot_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    package_name = _python_package_name(project_name)
    executable = provider.executable
    gates = (
        _command_gate(
            "bot-imports",
            "generated Discord bot import",
            [
                executable,
                "--offline",
                "run",
                "python",
                "-c",
                f"from {package_name}.bot import scaffold_status; print(scaffold_status())",
            ],
            "bot scaffold ready",
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
        ClaimSpec("bot-importable", "The generated bot module imports locally.", "local generated scaffold", ("bot-imports",)),
        ClaimSpec("command-registered", "The status command is registered without logging in.", "local generated scaffold", ("unit-tests",)),
        ClaimSpec("package-builds", "The generated scaffold builds a wheel and source distribution locally.", "local package build", ("package-build", "package-artifacts")),
        ClaimSpec(
            "gateway-runtime",
            "The bot connected to the Discord gateway.",
            "Discord gateway",
            (),
            True,
            "discord.Client.run was not launched by this suite.",
        ),
    )
    return VerificationSuite(
        "python-bot",
        "0.1",
        "generated Discord bot scaffold",
        gates,
        claims,
        "python",
        (
            "Gateway login and a real Discord token are outside this verification scope.",
        ),
    )
