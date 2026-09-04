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
        "}\n\n"
        "// 示例功能：一组可复用的字符串处理函数，均可被测试直接断言。\n"
        "export function capitalize(input: string): string {\n"
        "  if (input.length === 0) return input;\n"
        "  return input.charAt(0).toUpperCase() + input.slice(1).toLowerCase();\n"
        "}\n\n"
        "export function slugify(input: string): string {\n"
        "  return input\n"
        "    .toLowerCase()\n"
        "    .trim()\n"
        "    .replace(/[^a-z0-9]+/g, '-')\n"
        "    .replace(/^-+|-+$/g, '');\n"
        "}\n\n"
        "export function truncate(input: string, maxLength: number): string {\n"
        "  if (input.length <= maxLength) return input;\n"
        "  return `${input.slice(0, maxLength).trimEnd()}...`;\n"
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
        'import { capitalize, slugify, truncate } from "../dist/index.js";\n\n'
        'test("capitalize uppercases the first letter and lowercases the rest", () => {\n'
        '  assert.equal(capitalize("hello"), "Hello");\n'
        '  assert.equal(capitalize("hELLO WORLD"), "Hello world");\n'
        '  assert.equal(capitalize(""), "");\n'
        "});\n\n"
        'test("slugify turns text into a url-safe slug", () => {\n'
        '  assert.equal(slugify("Hello, World! 2026"), "hello-world-2026");\n'
        '  assert.equal(slugify("   spaces   "), "spaces");\n'
        "});\n\n"
        'test("truncate shortens long text with an ellipsis", () => {\n'
        '  assert.equal(truncate("hello world", 5), "hello...");\n'
        '  assert.equal(truncate("short", 20), "short");\n'
        "});\n"
    )


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
            "test": "tsc && node --test \"tests/*.test.js\"",
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
    (tests / "features.test.js").write_text(_render_features_test(), encoding="utf-8")
    run_command(
        [provider.executable, "install", "--no-fund", "--no-audit"],
        project_root,
        timeout=600,
    )
    return ScaffoldResult(
        command_result=scaffold,
        layout={"source": "src/", "tests": "tests/", "packaging": "package.json", "output": "dist/"},
    )
