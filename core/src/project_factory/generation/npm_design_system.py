"""Design-system tokens on the npm language root.

Storybook and a visual review are not verification gates.
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


def _render_tokens() -> str:
    return (
        "export const STATUS = 'design system scaffold ready';\n\n"
        "export const tokens = {\n"
        "  color: { fg: '#111111', bg: '#ffffff' },\n"
        "  space: { s: '4px', m: '8px' },\n"
        "} as const;\n"
    )


def _render_css() -> str:
    return (
        ":root {\n"
        "  --color-fg: #111111;\n"
        "  --color-bg: #ffffff;\n"
        "  --space-s: 4px;\n"
        "  --space-m: 8px;\n"
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
        'import { STATUS, tokens } from "../dist/tokens.js";\n\n'
        'test("tokens compile and css drawing exists", () => {\n'
        '  assert.equal(STATUS, "design system scaffold ready");\n'
        "  assert.equal(tokens.color.fg.startsWith('#'), true);\n"
        '  assert.equal(fs.existsSync("src/tokens.css"), true);\n'
        "});\n"
    )


def scaffold_npm_design_system(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "npm-design-system":
        raise RecipeError(f"Unsupported design-system scaffold recipe: {recipe}")
    project_root.mkdir(parents=True, exist_ok=False)
    scaffold = run_command([provider.executable, "init", "--yes"], project_root)
    package = {
        "name": _npm_package_name(project_name),
        "version": "0.1.0",
        "description": purpose,
        "private": True,
        "type": "module",
        "main": "./dist/tokens.js",
        "types": "./dist/tokens.d.ts",
        "scripts": {"build": "tsc", "test": "tsc && node --test tests/smoke.test.js"},
        "devDependencies": {"@types/node": TYPES_NODE_PIN, "typescript": TYPESCRIPT_PIN},
    }
    _write_json(project_root / "package.json", package)
    (project_root / "tsconfig.json").write_text(_render_tsconfig(), encoding="utf-8")
    source = project_root / "src"
    source.mkdir(parents=True, exist_ok=True)
    (source / "tokens.ts").write_text(_render_tokens(), encoding="utf-8")
    (source / "tokens.css").write_text(_render_css(), encoding="utf-8")
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "smoke.test.js").write_text(_render_smoke_test(), encoding="utf-8")
    run_command([provider.executable, "install", "--no-fund", "--no-audit"], project_root, timeout=600)
    return ScaffoldResult(
        command_result=scaffold,
        layout={"source": "src/", "tokens": "src/tokens.ts", "packaging": "package.json"},
    )
