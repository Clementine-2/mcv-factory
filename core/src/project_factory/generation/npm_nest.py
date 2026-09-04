"""NestJS HTTP body on the npm language root.

Binding a port is not a verification gate. Hono remains the default TS HTTP line.
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
from .npm_commander_cli import TYPES_NODE_PIN

NEST_PIN = "10.4.15"
REFLECT_PIN = "0.2.2"
RXJS_PIN = "7.8.1"


def _render_controller() -> str:
    return (
        "import { Controller, Get, Param } from '@nestjs/common';\n\n"
        "export interface HelloBody {\n"
        "  message: string;\n"
        "}\n\n"
        "export function buildHello(name: string): HelloBody {\n"
        "  const who = name.trim() || 'world';\n"
        "  return { message: `Hello, ${who}!` };\n"
        "}\n\n"
        "@Controller()\n"
        "export class HealthController {\n"
        "  @Get('health')\n"
        "  health(): { status: string; service: string } {\n"
        "    return { status: 'ok', service: 'http service scaffold ready' };\n"
        "  }\n\n"
        "  // 示例 endpoint：GET /hello/:name 返回 JSON 问候语。\n"
        "  @Get('hello/:name')\n"
        "  hello(@Param('name') name: string): HelloBody {\n"
        "    return buildHello(name);\n"
        "  }\n"
        "}\n"
    )


def _render_module() -> str:
    return (
        "import { Module } from '@nestjs/common';\n"
        "import { HealthController } from './health.controller';\n\n"
        "@Module({ controllers: [HealthController] })\n"
        "export class AppModule {}\n"
    )


def _render_main() -> str:
    return (
        "import 'reflect-metadata';\n"
        "import { NestFactory } from '@nestjs/core';\n"
        "import { AppModule } from './app.module';\n\n"
        "async function bootstrap(): Promise<void> {\n"
        "  const app = await NestFactory.create(AppModule);\n"
        "  await app.listen(0);\n"
        "}\n\n"
        "bootstrap();\n"
    )


def _render_tsconfig() -> str:
    return """{
  "compilerOptions": {
    "target": "ES2022",
    "module": "commonjs",
    "moduleResolution": "node",
    "strict": true,
    "declaration": true,
    "outDir": "dist",
    "rootDir": "src",
    "skipLibCheck": true,
    "experimentalDecorators": true,
    "emitDecoratorMetadata": true,
    "esModuleInterop": true
  },
  "include": ["src"]
}
"""


def _render_features_test() -> str:
    return (
        "require('reflect-metadata');\n"
        'const test = require("node:test");\n'
        'const assert = require("node:assert/strict");\n'
        'const { Test } = require("@nestjs/testing");\n'
        'const { HealthController, buildHello } = require("../dist/health.controller");\n\n'
        'test("buildHello formats a personalized message", () => {\n'
        '  assert.deepEqual(buildHello("Ada"), { message: "Hello, Ada!" });\n'
        '  assert.deepEqual(buildHello("  "), { message: "Hello, world!" });\n'
        "});\n\n"
        'test("hello route returns the personalized message through DI", async () => {\n'
        "  const moduleRef = await Test.createTestingModule({\n"
        "    controllers: [HealthController],\n"
        "  }).compile();\n"
        "  try {\n"
        "    const controller = moduleRef.get(HealthController);\n"
        "    const body = controller.hello('Ada');\n"
        '    assert.deepEqual(body, { message: "Hello, Ada!" });\n'
        "  } finally {\n"
        "    await moduleRef.close();\n"
        "  }\n"
        "});\n"
    )


def _render_smoke_test() -> str:
    return (
        "require('reflect-metadata');\n"
        'const test = require("node:test");\n'
        'const assert = require("node:assert/strict");\n'
        'const { Test } = require("@nestjs/testing");\n'
        'const { HealthController } = require("../dist/health.controller");\n\n'
        'test("health controller returns ok in-process", async () => {\n'
        "  const moduleRef = await Test.createTestingModule({\n"
        "    controllers: [HealthController],\n"
        "  }).compile();\n"
        "  const controller = moduleRef.get(HealthController);\n"
        "  const body = controller.health();\n"
        "  assert.equal(body.status, 'ok');\n"
        "  assert.equal(body.service, 'http service scaffold ready');\n"
        "  await moduleRef.close();\n"
        "});\n"
    )


def scaffold_npm_nest(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "npm-nest":
        raise RecipeError(f"Unsupported Nest scaffold recipe: {recipe}")
    project_root.mkdir(parents=True, exist_ok=False)
    scaffold = run_command([provider.executable, "init", "--yes"], project_root)
    package = {
        "name": _npm_package_name(project_name),
        "version": "0.1.0",
        "description": purpose,
        "private": True,
        "scripts": {"build": "tsc", "test": "tsc && node --test \"tests/*.test.js\""},
        "dependencies": {
            "@nestjs/common": NEST_PIN,
            "@nestjs/core": NEST_PIN,
            "@nestjs/platform-express": NEST_PIN,
            "reflect-metadata": REFLECT_PIN,
            "rxjs": RXJS_PIN,
        },
        "devDependencies": {
            "@nestjs/testing": NEST_PIN,
            "@types/node": TYPES_NODE_PIN,
            "typescript": TYPESCRIPT_PIN,
        },
    }
    _write_json(project_root / "package.json", package)
    (project_root / "tsconfig.json").write_text(_render_tsconfig(), encoding="utf-8")
    source = project_root / "src"
    source.mkdir(parents=True, exist_ok=True)
    (source / "health.controller.ts").write_text(_render_controller(), encoding="utf-8")
    (source / "app.module.ts").write_text(_render_module(), encoding="utf-8")
    (source / "main.ts").write_text(_render_main(), encoding="utf-8")
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "smoke.test.js").write_text(_render_smoke_test(), encoding="utf-8")
    (tests / "features.test.js").write_text(_render_features_test(), encoding="utf-8")
    run_command([provider.executable, "install", "--no-fund", "--no-audit"], project_root, timeout=600)
    return ScaffoldResult(
        command_result=scaffold,
        layout={"source": "src/", "app": "src/app.module.ts", "packaging": "package.json"},
    )
