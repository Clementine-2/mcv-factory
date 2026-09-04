"""Native WPF desktop app on the dotnet language root.

This is a user-project line. It is not the Factory's own WPF shell, not Electron,
and not a WebView wrapper.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..recipes import ProviderView, RecipeError, ScaffoldResult, run_command

_IDENT = re.compile(r"^[A-Z][A-Za-z0-9]*$")

XUNIT_PIN = "2.9.3"
XUNIT_RUNNER_PIN = "3.0.2"
TEST_SDK_PIN = "17.12.0"


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


def _render_counter(ident: str) -> str:
    return f"""namespace {ident};

/// <summary>
/// 纯逻辑计数器示例：不依赖任何 UI，可直接用 xUnit 单元测试。
/// 主窗口的"点击计数"按钮复用该类，避免把业务逻辑写死在界面代码里。
/// </summary>
public sealed class Counter
{{
    /// <summary>当前计数值。</summary>
    public int Value {{ get; private set; }}

    /// <summary>计数值加一，返回新值。</summary>
    public int Increment()
    {{
        Value += 1;
        return Value;
    }}

    /// <summary>计数值加上指定数量，返回新值。</summary>
    public int Add(int amount)
    {{
        Value += amount;
        return Value;
    }}

    /// <summary>重置计数值为零。</summary>
    public void Reset() => Value = 0;
}}
"""


def _render_main_window_xaml(ident: str) -> str:
    return f"""<Window x:Class="{ident}.MainWindow"
        xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        xmlns:d="http://schemas.microsoft.com/expression/blend/2008"
        xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"
        xmlns:local="clr-namespace:{ident}"
        mc:Ignorable="d"
        Title="{ident}" Height="450" Width="640">
    <StackPanel Margin="16">
        <TextBlock FontSize="18" Text="{ident} scaffold ready"/>
        <TextBlock x:Name="CounterText" Margin="0,16,0,0" FontSize="22" Text="点击次数：0"/>
        <Button x:Name="IncrementButton" Margin="0,8,0,0" Padding="12,6" Content="点击计数" Click="OnIncrementClick"/>
        <TextBox x:Name="EchoInput" Margin="0,16,0,0" Padding="6" Text="你好"/>
        <Button x:Name="EchoButton" Margin="0,8,0,0" Padding="12,6" Content="回显" Click="OnEchoClick"/>
        <TextBlock x:Name="EchoText" Margin="0,12,0,0" FontSize="16"/>
    </StackPanel>
</Window>
"""


def _render_main_window_code(ident: str) -> str:
    return f"""using System.Windows;

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

    private void OnIncrementClick(object sender, RoutedEventArgs e)
    {{
        _counter.Increment();
        CounterText.Text = $"点击次数：{{_counter.Value}}";
    }}

    private void OnEchoClick(object sender, RoutedEventArgs e)
    {{
        EchoText.Text = EchoInput.Text;
    }}
}}
"""


def _render_counter_test(ident: str) -> str:
    return f"""using {ident};
using Xunit;

public class CounterTests
{{
    [Fact]
    public void NewCounterStartsAtZero()
    {{
        var counter = new Counter();
        Assert.Equal(0, counter.Value);
    }}

    [Fact]
    public void IncrementRaisesValueByOne()
    {{
        var counter = new Counter();
        Assert.Equal(1, counter.Increment());
        Assert.Equal(2, counter.Increment());
        Assert.Equal(2, counter.Value);
    }}

    [Fact]
    public void AddRaisesValueByGivenAmount()
    {{
        var counter = new Counter();
        counter.Add(5);
        Assert.Equal(5, counter.Value);
    }}

    [Fact]
    public void ResetReturnsValueToZero()
    {{
        var counter = new Counter();
        counter.Increment();
        counter.Increment();
        counter.Reset();
        Assert.Equal(0, counter.Value);
    }}

    [Fact]
    public void ScaffoldStatusIsDefined()
    {{
        Assert.Equal("{ident} scaffold ready", ScaffoldStatus.Ready);
    }}
}}
"""


def _render_wpf_test_csproj(ident: str) -> str:
    return f"""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net9.0-windows</TargetFramework>
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
    <ProjectReference Include="../{ident}.csproj" />
  </ItemGroup>
</Project>
"""


_TESTS_EXCLUDE = """  <ItemGroup>
    <Compile Remove="tests/**" />
    <Content Remove="tests/**" />
    <None Remove="tests/**" />
    <EmbeddedResource Remove="tests/**" />
  </ItemGroup>
"""


def _patch_csproj_exclude_tests(csproj_path: Path) -> None:
    """让根项目忽略 tests/ 目录，避免把 xUnit 测试代码编进应用本身。"""
    text = csproj_path.read_text(encoding="utf-8")
    if "tests/**" in text:
        return
    marker = "</Project>"
    if marker not in text:
        raise RecipeError("WPF csproj did not contain </Project> to exclude tests/.")
    csproj_path.write_text(text.replace(marker, _TESTS_EXCLUDE + marker, 1), encoding="utf-8")


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
    (project_root / "Counter.cs").write_text(_render_counter(ident), encoding="utf-8")
    (project_root / "MainWindow.xaml").write_text(_render_main_window_xaml(ident), encoding="utf-8")
    (project_root / "MainWindow.xaml.cs").write_text(_render_main_window_code(ident), encoding="utf-8")
    _patch_csproj_exclude_tests(project_root / f"{ident}.csproj")
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / f"{ident}.Tests.csproj").write_text(_render_wpf_test_csproj(ident), encoding="utf-8")
    (tests / "CounterTests.cs").write_text(_render_counter_test(ident), encoding="utf-8")
    run_command(
        [provider.executable, "restore", str(tests / f"{ident}.Tests.csproj"), "--disable-build-servers"],
        project_root,
        timeout=300,
    )
    return ScaffoldResult(
        command_result=scaffold,
        layout={
            "source": f"{ident}.csproj",
            "window": "MainWindow.xaml",
            "app": "App.xaml",
            "tests": "tests/",
        },
    )
