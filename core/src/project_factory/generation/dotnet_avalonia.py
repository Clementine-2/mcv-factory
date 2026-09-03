"""Cross-platform desktop on the dotnet language root, Avalonia body.

Native Skia UI. Not Electron, not Tauri, not a WebView wrapper, and not the
Factory workbench shell. WPF remains the Windows-only csharp-desktop line.
"""

from __future__ import annotations

from pathlib import Path

from ..recipes import ProviderView, RecipeError, ScaffoldResult, run_command
from .dotnet_wpf import _csharp_ident, _render_status

AVALONIA_PIN = "11.2.8"


def _render_csproj(ident: str) -> str:
    pin = AVALONIA_PIN
    return f"""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>WinExe</OutputType>
    <TargetFramework>net9.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
    <RootNamespace>{ident}</RootNamespace>
    <BuiltInComInteropSupport>true</BuiltInComInteropSupport>
    <ApplicationTitle>{ident}</ApplicationTitle>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Avalonia" Version="{pin}" />
    <PackageReference Include="Avalonia.Desktop" Version="{pin}" />
    <PackageReference Include="Avalonia.Themes.Fluent" Version="{pin}" />
    <PackageReference Include="Avalonia.Fonts.Inter" Version="{pin}" />
  </ItemGroup>
</Project>
"""


def _render_program(ident: str) -> str:
    return f"""using Avalonia;
using System;

namespace {ident};

internal static class Program
{{
    [STAThread]
    public static void Main(string[] args) => BuildAvaloniaApp().StartWithClassicDesktopLifetime(args);

    public static AppBuilder BuildAvaloniaApp() =>
        AppBuilder.Configure<App>()
            .UsePlatformDetect()
            .WithInterFont()
            .LogToTrace();
}}
"""


def _render_app_axaml(ident: str) -> str:
    return f"""<Application xmlns="https://github.com/avaloniaui"
             xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
             x:Class="{ident}.App"
             RequestedThemeVariant="Default">
    <Application.Styles>
        <FluentTheme />
    </Application.Styles>
</Application>
"""


def _render_app_code(ident: str) -> str:
    return f"""using Avalonia;
using Avalonia.Controls.ApplicationLifetimes;
using Avalonia.Markup.Xaml;

namespace {ident};

public partial class App : Application
{{
    public override void Initialize() => AvaloniaXamlLoader.Load(this);

    public override void OnFrameworkInitializationCompleted()
    {{
        if (ApplicationLifetime is IClassicDesktopStyleApplicationLifetime desktop)
        {{
            desktop.MainWindow = new MainWindow();
        }}

        base.OnFrameworkInitializationCompleted();
    }}
}}
"""


def _render_window_axaml(ident: str) -> str:
    return f"""<Window xmlns="https://github.com/avaloniaui"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        x:Class="{ident}.MainWindow"
        Title="{ident}"
        Width="640"
        Height="400">
    <TextBlock Margin="16" FontSize="18" Text="{ident} scaffold ready"/>
</Window>
"""


def _render_window_code(ident: str) -> str:
    return f"""using Avalonia.Controls;

namespace {ident};

public partial class MainWindow : Window
{{
    public MainWindow()
    {{
        InitializeComponent();
    }}
}}
"""


def scaffold_dotnet_avalonia(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "dotnet-avalonia":
        raise RecipeError(f"Unsupported Avalonia scaffold recipe: {recipe}")
    ident = _csharp_ident(project_name)
    project_root.mkdir(parents=True, exist_ok=False)
    (project_root / f"{ident}.csproj").write_text(_render_csproj(ident), encoding="utf-8")
    (project_root / "Program.cs").write_text(_render_program(ident), encoding="utf-8")
    (project_root / "App.axaml").write_text(_render_app_axaml(ident), encoding="utf-8")
    (project_root / "App.axaml.cs").write_text(_render_app_code(ident), encoding="utf-8")
    (project_root / "MainWindow.axaml").write_text(_render_window_axaml(ident), encoding="utf-8")
    (project_root / "MainWindow.axaml.cs").write_text(_render_window_code(ident), encoding="utf-8")
    (project_root / "ScaffoldStatus.cs").write_text(_render_status(ident), encoding="utf-8")
    restore = run_command(
        [provider.executable, "restore", ident + ".csproj", "--disable-build-servers"],
        project_root,
        timeout=300,
    )
    return ScaffoldResult(
        command_result=restore,
        layout={
            "source": f"{ident}.csproj",
            "window": "MainWindow.axaml",
            "app": "App.axaml",
        },
    )
