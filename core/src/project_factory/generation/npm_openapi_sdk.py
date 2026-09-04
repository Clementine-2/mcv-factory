"""Generated TypeScript SDK from a frozen OpenAPI drawing.

Live upstream API sync is not a verification gate.
"""

from __future__ import annotations

from pathlib import Path

from ..recipes import (
    ProviderView,
    RecipeError,
    ScaffoldResult,
    _npm_package_name,
    _write_json,
    run_command,
)
from .npm_vite_web import TYPESCRIPT_PIN

OPENAPI_TS_PIN = "7.6.1"


def _render_spec() -> str:
    return """openapi: 3.0.3
info:
  title: Scaffold API
  version: 0.1.0
paths:
  /health:
    get:
      operationId: getHealth
      responses:
        "200":
          description: ok
          content:
            application/json:
              schema:
                type: object
                required: [status]
                properties:
                  status:
                    type: string
  /items:
    get:
      operationId: listItems
      responses:
        "200":
          description: list of items
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: "#/components/schemas/Item"
components:
  schemas:
    Item:
      type: object
      required: [id, name, price]
      properties:
        id:
          type: string
        name:
          type: string
        price:
          type: number
"""


def _render_client() -> str:
    return (
        "export const VERSION = '0.1.0';\n\n"
        "export type Health = { status: string };\n\n"
        "// 示例类型：对应 openapi.yaml 中的 Item schema。\n"
        "export type Item = { id: string; name: string; price: number };\n\n"
        "// 示例数据：SDK 方法的数据源，与 openapi.yaml 的 /items 路径对应。\n"
        "const items: Item[] = [\n"
        "  { id: 'a1', name: 'Widget', price: 9.99 },\n"
        "  { id: 'a2', name: 'Gadget', price: 19.99 },\n"
        "];\n\n"
        "export function scaffoldStatus(): string {\n"
        "  return 'generated sdk scaffold ready';\n"
        "}\n\n"
        "export function getHealth(): Health {\n"
        "  return { status: scaffoldStatus() };\n"
        "}\n\n"
        "// 示例方法：对应 /items 的 listItems 操作。\n"
        "export function listItems(): Item[] {\n"
        "  return items;\n"
        "}\n\n"
        "// 示例方法：按 id 查找单个 item。\n"
        "export function getItem(id: string): Item | undefined {\n"
        "  return items.find((item) => item.id === id);\n"
        "}\n"
    )


def _render_tsconfig() -> str:
    return """{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "strict": true,
    "declaration": true,
    "outDir": "dist",
    "rootDir": "src",
    "skipLibCheck": true
  },
  "include": ["src"]
}
"""


def _render_features_test() -> str:
    return (
        'import test from "node:test";\n'
        'import assert from "node:assert/strict";\n'
        'import { getItem, listItems } from "../dist/client.js";\n\n'
        'test("listItems returns the sample catalog", () => {\n'
        "  const result = listItems();\n"
        "  assert.equal(result.length, 2);\n"
        "  assert.equal(result[0].name, 'Widget');\n"
        "});\n\n"
        'test("getItem finds an item by id", () => {\n'
        '  assert.equal(getItem("a2")?.name, "Gadget");\n'
        '  assert.equal(getItem("a2")?.price, 19.99);\n'
        "});\n\n"
        'test("getItem returns undefined for an unknown id", () => {\n'
        '  assert.equal(getItem("nope"), undefined);\n'
        "});\n"
    )


def _render_smoke_test() -> str:
    return (
        'import test from "node:test";\n'
        'import assert from "node:assert/strict";\n'
        'import fs from "node:fs";\n'
        'import { getHealth, scaffoldStatus } from "../dist/client.js";\n\n'
        'test("openapi drawing exists", () => {\n'
        '  assert.equal(fs.existsSync("openapi.yaml"), true);\n'
        "});\n\n"
        'test("generated client returns scaffold health", () => {\n'
        '  assert.equal(scaffoldStatus(), "generated sdk scaffold ready");\n'
        '  assert.equal(getHealth().status, "generated sdk scaffold ready");\n'
        "});\n"
    )


def scaffold_npm_openapi_sdk(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "npm-openapi-sdk":
        raise RecipeError(f"Unsupported OpenAPI SDK scaffold recipe: {recipe}")
    project_root.mkdir(parents=True, exist_ok=False)
    scaffold = run_command([provider.executable, "init", "--yes"], project_root)
    package = {
        "name": _npm_package_name(project_name),
        "version": "0.1.0",
        "description": purpose,
        "private": True,
        "type": "module",
        "main": "./dist/client.js",
        "types": "./dist/client.d.ts",
        "scripts": {
            "generate": "openapi-typescript openapi.yaml -o src/schema.d.ts",
            "build": "tsc",
            "test": "tsc && node --test \"tests/*.test.js\"",
        },
        "devDependencies": {"openapi-typescript": OPENAPI_TS_PIN, "typescript": TYPESCRIPT_PIN},
    }
    _write_json(project_root / "package.json", package)
    (project_root / "openapi.yaml").write_text(_render_spec(), encoding="utf-8")
    (project_root / "tsconfig.json").write_text(_render_tsconfig(), encoding="utf-8")
    source = project_root / "src"
    source.mkdir(parents=True, exist_ok=True)
    (source / "client.ts").write_text(_render_client(), encoding="utf-8")
    (source / "schema.d.ts").write_text(
        "export interface paths { '/health': { get: { responses: { 200: { content: { 'application/json': { status: string } } } } } } }\n",
        encoding="utf-8",
    )
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "smoke.test.js").write_text(_render_smoke_test(), encoding="utf-8")
    (tests / "features.test.js").write_text(_render_features_test(), encoding="utf-8")
    run_command([provider.executable, "install", "--no-fund", "--no-audit"], project_root, timeout=600)
    run_command([provider.executable, "run", "generate"], project_root, timeout=180)
    return ScaffoldResult(
        command_result=scaffold,
        layout={"spec": "openapi.yaml", "source": "src/", "packaging": "package.json"},
    )
