"""TypeScript library on the npm language root.

This is a library profile, not a web UI. Pins are tested versions.
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


def _render_index() -> str:
    return (
        'export const VERSION = "0.1.0";\n\n'
        "export function scaffoldStatus(): string {\n"
        '  return "typescript library scaffold ready";\n'
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
        'import { VERSION, scaffoldStatus } from "../dist/index.js";\n\n'
        'test("library compiles and imports", () => {\n'
        '  assert.equal(VERSION, "0.1.0");\n'
        '  assert.equal(scaffoldStatus(), "typescript library scaffold ready");\n'
        "});\n"
    )


def scaffold_npm_ts_library(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "npm-ts-library":
        raise RecipeError(f"Unsupported TypeScript library scaffold recipe: {recipe}")
    project_root.mkdir(parents=True, exist_ok=False)
    scaffold = run_command([provider.executable, "init", "--yes"], project_root)
    package = {
        "name": _npm_package_name(project_name),
        "version": "0.1.0",
        "description": purpose,
        "private": True,
        "type": "module",
        "main": "./dist/index.js",
        "types": "./dist/index.d.ts",
        "exports": "./dist/index.js",
        "scripts": {
            "build": "tsc",
            "test": "tsc && node --test tests/smoke.test.js",
        },
        "files": ["dist", "README.md", "AGENTS.md", ".project", "project.lock.json"],
        "devDependencies": {"typescript": TYPESCRIPT_PIN},
    }
    _write_json(project_root / "package.json", package)
    (project_root / "tsconfig.json").write_text(_render_tsconfig(), encoding="utf-8")
    source = project_root / "src"
    source.mkdir(parents=True, exist_ok=True)
    (source / "index.ts").write_text(_render_index(), encoding="utf-8")
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "smoke.test.js").write_text(_render_smoke_test(), encoding="utf-8")
    run_command(
        [provider.executable, "install", "--no-fund", "--no-audit"],
        project_root,
        timeout=600,
    )
    return ScaffoldResult(
        command_result=scaffold,
        layout={"source": "src/", "tests": "tests/", "packaging": "package.json", "output": "dist/"},
    )
