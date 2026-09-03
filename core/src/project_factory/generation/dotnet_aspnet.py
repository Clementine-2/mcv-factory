"""Minimal ASP.NET Core HTTP service on the dotnet language root.

Aligns with the service work product. Not a full-stack template. Binding a
port is not a verification gate.
"""

from __future__ import annotations

from pathlib import Path

from ..recipes import ProviderView, RecipeError, ScaffoldResult, run_command
from .dotnet_wpf import _csharp_ident

ASPNET_TESTING_PIN = "9.0.0"
XUNIT_PIN = "2.9.3"
XUNIT_RUNNER_PIN = "3.0.2"
TEST_SDK_PIN = "17.12.0"


def _render_csproj(ident: str) -> str:
    return f"""<Project Sdk="Microsoft.NET.Sdk.Web">
  <PropertyGroup>
    <TargetFramework>net9.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
    <RootNamespace>{ident}</RootNamespace>
  </PropertyGroup>
  <ItemGroup>
    <Compile Remove="tests/**" />
    <Content Remove="tests/**" />
    <None Remove="tests/**" />
    <EmbeddedResource Remove="tests/**" />
  </ItemGroup>
</Project>
"""


def _render_program(ident: str) -> str:
    return f"""using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;

var builder = WebApplication.CreateBuilder(args);
var app = builder.Build();
app.MapGet("/health", () => Results.Json(new {{ status = "ok", service = "{ident}" }}));
app.Run();

public partial class Program {{ }}
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
    <PackageReference Include="Microsoft.AspNetCore.Mvc.Testing" Version="{ASPNET_TESTING_PIN}" />
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


def _render_health_test() -> str:
    return """using System.Net;
using Microsoft.AspNetCore.Mvc.Testing;
using Xunit;

public class HealthTests : IClassFixture<WebApplicationFactory<Program>>
{
    private readonly WebApplicationFactory<Program> _factory;

    public HealthTests(WebApplicationFactory<Program> factory)
    {
        _factory = factory;
    }

    [Fact]
    public async Task HealthReturnsOk()
    {
        var client = _factory.CreateClient();
        var response = await client.GetAsync("/health");
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var body = await response.Content.ReadAsStringAsync();
        Assert.Contains("ok", body);
    }
}
"""


def scaffold_dotnet_aspnet(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "dotnet-aspnet":
        raise RecipeError(f"Unsupported ASP.NET scaffold recipe: {recipe}")
    ident = _csharp_ident(project_name)
    project_root.mkdir(parents=True, exist_ok=False)
    (project_root / f"{ident}.csproj").write_text(_render_csproj(ident), encoding="utf-8")
    (project_root / "Program.cs").write_text(_render_program(ident), encoding="utf-8")
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / f"{ident}.Tests.csproj").write_text(_render_test_csproj(ident), encoding="utf-8")
    (tests / "HealthTests.cs").write_text(_render_health_test(), encoding="utf-8")
    restore = run_command(
        [provider.executable, "restore", str(tests / f"{ident}.Tests.csproj"), "--disable-build-servers"],
        project_root,
        timeout=300,
    )
    return ScaffoldResult(
        command_result=restore,
        layout={
            "source": f"{ident}.csproj",
            "entry": "Program.cs",
            "tests": "tests/",
        },
    )
