"""Minimal C# class library on the dotnet language root.

NuGet.org publication is not a verification gate.
"""

from __future__ import annotations

from pathlib import Path

from ..recipes import ProviderView, RecipeError, ScaffoldResult, run_command
from .dotnet_wpf import _csharp_ident

XUNIT_PIN = "2.9.3"
XUNIT_RUNNER_PIN = "3.0.2"
TEST_SDK_PIN = "17.12.0"


def _render_csproj(ident: str) -> str:
    return f"""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net9.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
    <RootNamespace>{ident}</RootNamespace>
    <Version>0.1.0</Version>
    <IsPackable>true</IsPackable>
  </PropertyGroup>
  <ItemGroup>
    <Compile Remove="tests/**" />
    <Content Remove="tests/**" />
    <None Remove="tests/**" />
    <EmbeddedResource Remove="tests/**" />
  </ItemGroup>
</Project>
"""


def _render_status(ident: str) -> str:
    return f"""namespace {ident};

public static class ScaffoldStatus
{{
    public const string Ready = "{ident} scaffold ready";
}}
"""


def _render_text(ident: str) -> str:
    return f"""namespace {ident};

public static class Text
{{
    public static string Normalize(string value)
    {{
        return value.Trim();
    }}
}}
"""


def _render_test_csproj(ident: str) -> str:
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
    <ProjectReference Include="../{ident}.csproj" />
  </ItemGroup>
</Project>
"""


def _render_text_test(ident: str) -> str:
    return f"""using {ident};
using Xunit;

public class TextTests
{{
    [Fact]
    public void NormalizeTrimsAndReportsReady()
    {{
        Assert.Equal("ok", Text.Normalize("  ok  "));
        Assert.Equal("{ident} scaffold ready", ScaffoldStatus.Ready);
    }}
}}
"""


def scaffold_dotnet_library(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "dotnet-library":
        raise RecipeError(f"Unsupported C# library scaffold recipe: {recipe}")
    ident = _csharp_ident(project_name)
    project_root.mkdir(parents=True, exist_ok=False)
    (project_root / f"{ident}.csproj").write_text(_render_csproj(ident), encoding="utf-8")
    (project_root / "ScaffoldStatus.cs").write_text(_render_status(ident), encoding="utf-8")
    (project_root / "Text.cs").write_text(_render_text(ident), encoding="utf-8")
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / f"{ident}.Tests.csproj").write_text(_render_test_csproj(ident), encoding="utf-8")
    (tests / "TextTests.cs").write_text(_render_text_test(ident), encoding="utf-8")
    restore = run_command(
        [provider.executable, "restore", str(tests / f"{ident}.Tests.csproj"), "--disable-build-servers"],
        project_root,
        timeout=300,
    )
    return ScaffoldResult(
        command_result=restore,
        layout={
            "source": f"{ident}.csproj",
            "entry": "Text.cs",
            "tests": "tests/",
        },
    )
