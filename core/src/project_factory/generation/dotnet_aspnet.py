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

// 内存中的示例数据存储（真实 API 示例，不依赖外部数据库，方便单元测试）。
var items = new List<Item>
{{
    new(1, "示例项 A"),
    new(2, "示例项 B"),
}};

app.MapGet("/health", () => Results.Json(new {{ status = "ok", service = "{ident}" }}));

// 列出全部数据项
app.MapGet("/api/items", () => Results.Json(items));

// 按 id 查询单个数据项
app.MapGet("/api/items/{{id:int}}", (int id) =>
{{
    var item = items.FirstOrDefault(i => i.Id == id);
    return item is null
        ? Results.NotFound(new {{ error = $"item {{id}} not found" }})
        : Results.Json(item);
}});

// 新增数据项
app.MapPost("/api/items", (CreateItemRequest request) =>
{{
    if (string.IsNullOrWhiteSpace(request.Name))
    {{
        return Results.BadRequest(new {{ error = "name is required" }});
    }}
    var nextId = items.Max(i => i.Id) + 1;
    var item = new Item(nextId, request.Name.Trim());
    items.Add(item);
    return Results.Created($"/api/items/{{item.Id}}", item);
}});

// 删除数据项
app.MapDelete("/api/items/{{id:int}}", (int id) =>
{{
    var removed = items.RemoveAll(i => i.Id == id);
    return removed == 0
        ? Results.NotFound(new {{ error = $"item {{id}} not found" }})
        : Results.NoContent();
}});

app.Run();

/// <summary>示例数据项。</summary>
public record Item(int Id, string Name);

/// <summary>创建数据项的请求体。</summary>
public record CreateItemRequest(string Name);

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


def _render_items_api_test() -> str:
    return """using System.Net;
using System.Net.Http.Json;
using Microsoft.AspNetCore.Mvc.Testing;
using Xunit;

public class ItemsApiTests
{
    [Fact]
    public async Task GetItemsReturnsSeededList()
    {
        using var factory = new WebApplicationFactory<Program>();
        var client = factory.CreateClient();

        var response = await client.GetAsync("/api/items");
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var items = await response.Content.ReadFromJsonAsync<Item[]>();
        Assert.NotNull(items);
        Assert.Equal(2, items!.Length);
        Assert.Equal("示例项 A", items[0].Name);
        Assert.Equal("示例项 B", items[1].Name);
    }

    [Fact]
    public async Task GetItemReturnsNotFoundForMissingId()
    {
        using var factory = new WebApplicationFactory<Program>();
        var client = factory.CreateClient();

        var response = await client.GetAsync("/api/items/999");
        Assert.Equal(HttpStatusCode.NotFound, response.StatusCode);
    }

    [Fact]
    public async Task PostItemAddsToCollection()
    {
        using var factory = new WebApplicationFactory<Program>();
        var client = factory.CreateClient();

        var createResponse = await client.PostAsJsonAsync("/api/items", new CreateItemRequest("示例项 C"));
        Assert.Equal(HttpStatusCode.Created, createResponse.StatusCode);

        var listResponse = await client.GetAsync("/api/items");
        var items = await listResponse.Content.ReadFromJsonAsync<Item[]>();
        Assert.NotNull(items);
        Assert.Equal(3, items!.Length);
        Assert.Contains(items, item => item.Name == "示例项 C");
    }

    [Fact]
    public async Task PostItemRejectsEmptyName()
    {
        using var factory = new WebApplicationFactory<Program>();
        var client = factory.CreateClient();

        var createResponse = await client.PostAsJsonAsync("/api/items", new CreateItemRequest("   "));
        Assert.Equal(HttpStatusCode.BadRequest, createResponse.StatusCode);
    }

    [Fact]
    public async Task DeleteItemRemovesFromCollection()
    {
        using var factory = new WebApplicationFactory<Program>();
        var client = factory.CreateClient();

        var deleteResponse = await client.DeleteAsync("/api/items/1");
        Assert.Equal(HttpStatusCode.NoContent, deleteResponse.StatusCode);

        var getResponse = await client.GetAsync("/api/items/1");
        Assert.Equal(HttpStatusCode.NotFound, getResponse.StatusCode);
    }

    [Fact]
    public async Task DeleteMissingItemReturnsNotFound()
    {
        using var factory = new WebApplicationFactory<Program>();
        var client = factory.CreateClient();

        var deleteResponse = await client.DeleteAsync("/api/items/999");
        Assert.Equal(HttpStatusCode.NotFound, deleteResponse.StatusCode);
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
    (tests / "ItemsApiTests.cs").write_text(_render_items_api_test(), encoding="utf-8")
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
