"""Cross-platform desktop on the dotnet language root, Avalonia body.

Native Skia UI. Not Electron, not Tauri, not a WebView wrapper, and not the
Factory workbench shell. WPF remains the Windows-only csharp-desktop line.
"""

from __future__ import annotations

from pathlib import Path

from ..recipes import ProviderView, RecipeError, ScaffoldResult, run_command
from .dotnet_wpf import (
    XUNIT_PIN,
    XUNIT_RUNNER_PIN,
    TEST_SDK_PIN,
    _csharp_ident,
    _render_counter,
    _render_counter_test,
    _render_status,
)

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
  <ItemGroup>
    <Compile Remove="tests/**" />
    <Content Remove="tests/**" />
    <None Remove="tests/**" />
    <EmbeddedResource Remove="tests/**" />
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
    <StackPanel Margin="16" Spacing="8">
        <TextBlock FontSize="18" Text="{ident} scaffold ready"/>
        <TextBlock x:Name="CounterText" FontSize="22" Text="点击次数：0"/>
        <Button x:Name="IncrementButton" Content="点击计数" Click="OnIncrementClick"/>
        <TextBox x:Name="EchoInput" Text="你好" Watermark="输入内容后点击回显"/>
        <Button x:Name="EchoButton" Content="回显" Click="OnEchoClick"/>
        <TextBlock x:Name="EchoText" FontSize="16"/>
    </StackPanel>
</Window>
"""


def _render_window_code(ident: str) -> str:
    return f"""using Avalonia.Controls;
using Avalonia.Interactivity;

namespace {ident};

/// <summary>
/// 主窗口示例交互：按钮点击计数 + 文本框回显。
/// 计数逻辑复用纯逻辑类 Counter，便于单元测试。
/// </summary>
public partial class MainWindow : Window
{{
    private readonly Counter _counter = new();

    public MainWindow()
    {{
        InitializeComponent();
    }}

    private void OnIncrementClick(object? sender, RoutedEventArgs e)
    {{
        _counter.Increment();
        CounterText.Text = $"点击次数：{{_counter.Value}}";
    }}

    private void OnEchoClick(object? sender, RoutedEventArgs e)
    {{
        EchoText.Text = EchoInput.Text;
    }}
}}
"""


def _render_avalonia_test_csproj(ident: str, csproj_name: str) -> str:
    return f"""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net9.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
    <IsPackable>false</IsPackable>
    <RootNamespace>{ident}.Tests</RootNamespace>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Microsoft.NET.Test.Sdk" Version="{TEST_SDK_PIN}" />
    <PackageReference Include="xunit" Version="{XUNIT_PIN}" />
    <PackageReference Include="xunit.runner.visualstudio" Version="{XUNIT_RUNNER_PIN}">
      <PrivateAssets>all</PrivateAssets>
      <IncludeAssets>runtime; build; native; contentfiles; analyzers; buildtransitive</IncludeAssets>
    </PackageReference>
  </ItemGroup>
  <ItemGroup>
    <ProjectReference Include="../{csproj_name}.csproj" />
  </ItemGroup>
</Project>
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
    # Robustness: NuGet treats the .csproj file name as the project identity. When
    # the project is named exactly like a referenced package (e.g. a requirement
    # like "Avalonia desktop app" yields project name "Avalonia"), restore fails
    # with NU1108 "Avalonia -> Avalonia (>= 11.2.8)" (project seen as self-loop).
    # Use a distinct file name so the project identity differs from every package.
    csproj_name = ident
    referenced = {"Avalonia", "Avalonia.Desktop", "Avalonia.Themes.Fluent", "Avalonia.Fonts.Inter"}
    if csproj_name in referenced or csproj_name.casefold() in {p.casefold() for p in referenced}:
        csproj_name = f"{ident}.App"
    project_root.mkdir(parents=True, exist_ok=False)
    (project_root / f"{csproj_name}.csproj").write_text(_render_csproj(ident), encoding="utf-8")
    (project_root / "Program.cs").write_text(_render_program(ident), encoding="utf-8")
    (project_root / "App.axaml").write_text(_render_app_axaml(ident), encoding="utf-8")
    (project_root / "App.axaml.cs").write_text(_render_app_code(ident), encoding="utf-8")
    (project_root / "MainWindow.axaml").write_text(_render_window_axaml(ident), encoding="utf-8")
    (project_root / "MainWindow.axaml.cs").write_text(_render_window_code(ident), encoding="utf-8")
    (project_root / "ScaffoldStatus.cs").write_text(_render_status(ident), encoding="utf-8")
    (project_root / "Counter.cs").write_text(_render_counter(ident), encoding="utf-8")
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    # 测试项目引用主项目时使用与 NuGet 包区分开的 csproj 文件名，避免 NU1108 回退逻辑被破坏。
    (tests / f"{ident}.Tests.csproj").write_text(
        _render_avalonia_test_csproj(ident, csproj_name), encoding="utf-8"
    )
    (tests / "CounterTests.cs").write_text(_render_counter_test(ident), encoding="utf-8")
    restore = run_command(
        [provider.executable, "restore", csproj_name + ".csproj", "--disable-build-servers"],
        project_root,
        timeout=300,
    )
    return ScaffoldResult(
        command_result=restore,
        layout={
            "source": f"{csproj_name}.csproj",
            "window": "MainWindow.axaml",
            "app": "App.axaml",
            "tests": "tests/",
        },
    )
