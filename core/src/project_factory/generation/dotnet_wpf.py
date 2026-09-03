"""Native WPF desktop app on the dotnet language root.

This is a user-project line. It is not the Factory's own WPF shell, not Electron,
and not a WebView wrapper.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..recipes import ProviderView, RecipeError, ScaffoldResult, run_command

_IDENT = re.compile(r"^[A-Z][A-Za-z0-9]*$")


def _csharp_ident(project_name: str) -> str:
    parts = [part for part in re.split(r"[^A-Za-z0-9]+", project_name) if part]
    if not parts:
        raise RecipeError(f"Project name {project_name!r} cannot map to a C# identifier.")
    ident = "".join(part[:1].upper() + part[1:] for part in parts)
    if ident[0].isdigit():
        ident = "App" + ident
    if not _IDENT.fullmatch(ident):
        raise RecipeError(f"Project name {project_name!r} cannot map to a C# identifier.")
    return ident


def _render_status(ident: str) -> str:
    return f"""namespace {ident};

public static class ScaffoldStatus
{{
    public const string Ready = "{ident} scaffold ready";
}}
"""


def scaffold_dotnet_wpf(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "dotnet-wpf":
        raise RecipeError(f"Unsupported WPF scaffold recipe: {recipe}")
    ident = _csharp_ident(project_name)
    scaffold = run_command(
        [
            provider.executable,
            "new",
            "wpf",
            "-n",
            ident,
            "-o",
            str(project_root),
            "-f",
            "net9.0",
            "--no-restore",
        ],
        staging_root,
        timeout=120,
    )
    (project_root / "ScaffoldStatus.cs").write_text(_render_status(ident), encoding="utf-8")
    xaml_path = project_root / "MainWindow.xaml"
    xaml = xaml_path.read_text(encoding="utf-8-sig")
    marker = "<Grid>"
    if marker not in xaml:
        raise RecipeError("Official WPF MainWindow.xaml did not contain a Grid to overlay.")
    replacement = (
        "<Grid>\n"
        f'        <TextBlock Margin="16" FontSize="18" Text="{ident} scaffold ready"/>'
    )
    xaml_path.write_text(xaml.replace(marker, replacement, 1), encoding="utf-8")
    run_command(
        [provider.executable, "restore", ident + ".csproj", "--disable-build-servers"],
        project_root,
        timeout=180,
    )
    return ScaffoldResult(
        command_result=scaffold,
        layout={
            "source": f"{ident}.csproj",
            "window": "MainWindow.xaml",
            "app": "App.xaml",
        },
    )
