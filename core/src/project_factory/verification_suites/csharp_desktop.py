from __future__ import annotations

from ..verification import (
    ClaimSpec,
    GateSpec,
    ProviderView,
    VerificationSuite,
    _command_gate,
)


def build_csharp_desktop_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "wpf-build",
            "generated WPF project build",
            [executable, "build", "--nologo", "--disable-build-servers"],
        ),
        GateSpec(
            "wpf-artifacts",
            "compiled Windows desktop artifacts",
            "artifact",
            artifact_patterns=(
                "bin/Debug/net9.0-windows/*.dll",
                "bin/Debug/net9.0-windows/*.exe",
            ),
            min_artifacts=1,
        ),
    )
    claims = (
        ClaimSpec("wpf-builds", "The generated WPF project compiles locally.", "local generated scaffold", ("wpf-build", "wpf-artifacts")),
        ClaimSpec(
            "window-shown",
            "A desktop window was displayed and interacted with.",
            "interactive desktop runtime",
            (),
            True,
            "The window was not launched by this suite.",
        ),
        ClaimSpec(
            "cross-platform-desktop",
            "The app runs on non-Windows desktops.",
            "non-Windows desktop runtime",
            (),
            True,
            "This profile targets net9.0-windows WPF. It is not a cross-platform desktop shell.",
        ),
    )
    return VerificationSuite(
        "csharp-desktop",
        "0.1",
        "generated WPF desktop scaffold",
        gates,
        claims,
        "dotnet",
        (
            "This is a user-project WPF line, not the Factory workbench shell.",
            "Electron and WebView wrappers are out of scope.",
            "Showing the window is not a verification gate.",
        ),
    )
