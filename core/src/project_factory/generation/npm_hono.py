"""Hono HTTP service on the npm language root.

Binding a port is not a verification gate.
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

HONO_PIN = "4.7.4"


def _render_app() -> str:
    return (
        "import { Hono } from 'hono';\n\n"
        "export const STATUS = 'http service scaffold ready';\n\n"
        "export const app = new Hono();\n"
        "app.get('/health', (context) => context.json({ status: 'ok', service: STATUS }));\n"
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
        'import { app, STATUS } from "../dist/app.js";\n\n'
        'test("health returns ok in-process", async () => {\n'
        "  const response = await app.request('/health');\n"
        "  assert.equal(response.status, 200);\n"
        "  const body = await response.json();\n"
        "  assert.equal(body.status, 'ok');\n"
        "  assert.equal(body.service, STATUS);\n"
        "});\n"
    )


def scaffold_npm_hono(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "npm-hono":
        raise RecipeError(f"Unsupported Hono scaffold recipe: {recipe}")
    project_root.mkdir(parents=True, exist_ok=False)
    scaffold = run_command([provider.executable, "init", "--yes"], project_root)
    package = {
        "name": _npm_package_name(project_name),
        "version": "0.1.0",
        "description": purpose,
        "private": True,
        "type": "module",
        "scripts": {"build": "tsc", "test": "tsc && node --test tests/smoke.test.js"},
        "dependencies": {"hono": HONO_PIN},
        "devDependencies": {"@types/node": TYPES_NODE_PIN, "typescript": TYPESCRIPT_PIN},
    }
    _write_json(project_root / "package.json", package)
    (project_root / "tsconfig.json").write_text(_render_tsconfig(), encoding="utf-8")
    source = project_root / "src"
    source.mkdir(parents=True, exist_ok=True)
    (source / "app.ts").write_text(_render_app(), encoding="utf-8")
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "smoke.test.js").write_text(_render_smoke_test(), encoding="utf-8")
    run_command([provider.executable, "install", "--no-fund", "--no-audit"], project_root, timeout=600)
    return ScaffoldResult(
        command_result=scaffold,
        layout={"source": "src/", "app": "src/app.ts", "packaging": "package.json"},
    )
