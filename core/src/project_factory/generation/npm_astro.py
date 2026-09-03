"""Astro static site on the npm language root.

astro preview/dev is not a verification gate.
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

ASTRO_PIN = "5.5.5"


def _render_config() -> str:
    return "import { defineConfig } from 'astro/config';\n\nexport default defineConfig({});\n"


def _render_index() -> str:
    return (
        "---\n"
        "---\n"
        "<html lang=\"en\">\n"
        "<head><meta charset=\"utf-8\"><title>Astro scaffold</title></head>\n"
        "<body><main>static site scaffold ready</main></body>\n"
        "</html>\n"
    )


def _render_tsconfig() -> str:
    return """{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "skipLibCheck": true
  }
}
"""


def _render_smoke_test() -> str:
    return (
        'import test from "node:test";\n'
        'import assert from "node:assert/strict";\n'
        'import fs from "node:fs";\n\n'
        'test("astro drawing files exist", () => {\n'
        '  assert.equal(fs.existsSync("astro.config.mjs"), true);\n'
        '  assert.equal(fs.existsSync("src/pages/index.astro"), true);\n'
        "  const pkg = JSON.parse(fs.readFileSync(\"package.json\", \"utf8\"));\n"
        f'  assert.equal(pkg.dependencies.astro, "{ASTRO_PIN}");\n'
        "});\n"
    )


def scaffold_npm_astro(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "npm-astro":
        raise RecipeError(f"Unsupported Astro scaffold recipe: {recipe}")
    project_root.mkdir(parents=True, exist_ok=False)
    scaffold = run_command([provider.executable, "init", "--yes"], project_root)
    package = {
        "name": _npm_package_name(project_name),
        "version": "0.1.0",
        "description": purpose,
        "private": True,
        "type": "module",
        "scripts": {"dev": "astro dev", "build": "astro build", "preview": "astro preview", "test": "node --test tests/smoke.test.js"},
        "dependencies": {"astro": ASTRO_PIN},
        "devDependencies": {"typescript": TYPESCRIPT_PIN},
    }
    _write_json(project_root / "package.json", package)
    (project_root / "astro.config.mjs").write_text(_render_config(), encoding="utf-8")
    (project_root / "tsconfig.json").write_text(_render_tsconfig(), encoding="utf-8")
    pages = project_root / "src" / "pages"
    pages.mkdir(parents=True, exist_ok=True)
    (pages / "index.astro").write_text(_render_index(), encoding="utf-8")
    (project_root / "src" / "env.d.ts").write_text('/// <reference types="astro/client" />\n', encoding="utf-8")
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "smoke.test.js").write_text(_render_smoke_test(), encoding="utf-8")
    run_command([provider.executable, "install", "--no-fund", "--no-audit"], project_root, timeout=600)
    return ScaffoldResult(
        command_result=scaffold,
        layout={"source": "src/pages/", "config": "astro.config.mjs", "packaging": "package.json", "output": "dist/"},
    )
