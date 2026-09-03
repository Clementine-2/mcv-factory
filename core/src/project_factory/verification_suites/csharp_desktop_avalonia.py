from __future__ import annotations

from ..verification import (
    ClaimSpec,
    GateSpec,
    ProviderView,
    VerificationSuite,
    _command_gate,
)


def build_csharp_desktop_avalonia_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "avalonia-build",
            "generated Avalonia project build",
            [executable, "build", "--nologo", "--disable-build-servers"],
        ),
        GateSpec(
            "avalonia-artifacts",
            "compiled cross-platform desktop artifacts",
            "artifact",
            artifact_patterns=(
                "bin/Debug/net9.0/*.dll",
                "bin/Debug/net9.0/*.exe",
            ),
            min_artifacts=1,
        ),
    )
    claims = (
        ClaimSpec(
            "avalonia-builds",
            "The generated Avalonia project compiles locally.",
            "local generated scaffold",
            ("avalonia-build", "avalonia-artifacts"),
        ),
        ClaimSpec(
            "window-shown",
            "A desktop window was displayed and interacted with.",
            "interactive desktop runtime",
            (),
            True,
            "The window was not launched by this suite.",
        ),
    )
    return VerificationSuite(
        "csharp-desktop-avalonia",
        "0.1",
        "generated Avalonia cross-platform desktop scaffold",
        gates,
        claims,
        "dotnet",
        (
            "This is a user-project Avalonia line, not the Factory workbench shell.",
            "Electron, Tauri, and WebView wrappers are out of scope.",
            "Showing the window is not a verification gate.",
            "iced on Windows GNU was not shipped: the host rustc cannot complete windows-sys linking.",
        ),
    )
