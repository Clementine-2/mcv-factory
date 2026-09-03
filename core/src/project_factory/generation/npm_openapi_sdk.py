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
"""


def _render_client() -> str:
    return (
        "export const VERSION = '0.1.0';\n\n"
        "export type Health = { status: string };\n\n"
        "export function scaffoldStatus(): string {\n"
        "  return 'generated sdk scaffold ready';\n"
        "}\n\n"
        "export function getHealth(): Health {\n"
        "  return { status: scaffoldStatus() };\n"
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
            "test": "tsc && node --test tests/smoke.test.js",
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
    run_command([provider.executable, "install", "--no-fund", "--no-audit"], project_root, timeout=600)
    run_command([provider.executable, "run", "generate"], project_root, timeout=180)
    return ScaffoldResult(
        command_result=scaffold,
        layout={"spec": "openapi.yaml", "source": "src/", "packaging": "package.json"},
    )
