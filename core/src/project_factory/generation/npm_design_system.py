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


def _render_components() -> str:
    return """// 示例原子组件：一组可复用的设计系统工具函数，均可被测试直接断言。
export type ButtonVariant = 'primary' | 'secondary' | 'ghost';

export function buttonClass(variant: ButtonVariant = 'primary'): string {
  const variants: Record<ButtonVariant, string> = {
    primary: 'pf-button--primary',
    secondary: 'pf-button--secondary',
    ghost: 'pf-button--ghost',
  };
  return `pf-button ${variants[variant]}`;
}

export function spacing(...steps: number[]): string {
  return steps.map((step) => `${step * 4}px`).join(' ');
}

export function contrastText(background: string): string {
  const hex = background.replace('#', '');
  const value = parseInt(hex, 16);
  const r = (value >> 16) & 0xff;
  const g = (value >> 8) & 0xff;
  const b = value & 0xff;
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.6 ? '#111111' : '#ffffff';
}
"""


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


def _render_components_test() -> str:
    return (
        'import test from "node:test";\n'
        'import assert from "node:assert/strict";\n'
        'import { buttonClass, contrastText, spacing } from "../dist/components.js";\n\n'
        'test("buttonClass returns a primary class by default", () => {\n'
        '  assert.equal(buttonClass(), "pf-button pf-button--primary");\n'
        '  assert.equal(buttonClass("secondary"), "pf-button pf-button--secondary");\n'
        '  assert.equal(buttonClass("ghost"), "pf-button pf-button--ghost");\n'
        "});\n\n"
        'test("spacing converts scale steps to px", () => {\n'
        '  assert.equal(spacing(1), "4px");\n'
        '  assert.equal(spacing(1, 2), "4px 8px");\n'
        "});\n\n"
        'test("contrastText picks a readable ink color", () => {\n'
        '  assert.equal(contrastText("#ffffff"), "#111111");\n'
        '  assert.equal(contrastText("#000000"), "#ffffff");\n'
        "});\n"
    )


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
        "scripts": {"build": "tsc", "test": "tsc && node --test \"tests/*.test.js\""},
        "devDependencies": {"@types/node": TYPES_NODE_PIN, "typescript": TYPESCRIPT_PIN},
    }
    _write_json(project_root / "package.json", package)
    (project_root / "tsconfig.json").write_text(_render_tsconfig(), encoding="utf-8")
    source = project_root / "src"
    source.mkdir(parents=True, exist_ok=True)
    (source / "tokens.ts").write_text(_render_tokens(), encoding="utf-8")
    (source / "components.ts").write_text(_render_components(), encoding="utf-8")
    (source / "tokens.css").write_text(_render_css(), encoding="utf-8")
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "smoke.test.js").write_text(_render_smoke_test(), encoding="utf-8")
    (tests / "components.test.js").write_text(_render_components_test(), encoding="utf-8")
    run_command([provider.executable, "install", "--no-fund", "--no-audit"], project_root, timeout=600)
    return ScaffoldResult(
        command_result=scaffold,
        layout={"source": "src/", "tokens": "src/tokens.ts", "packaging": "package.json"},
    )
