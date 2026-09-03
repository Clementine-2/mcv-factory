"""WXT Manifest V3 successor body on the npm language root.

Old hand-written browser-extension-js stays. This plugin does not open a browser.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..recipes import (
    ProviderView,
    RecipeError,
    ScaffoldResult,
    _npm_package_name,
    _write_json,
    run_command,
)

WXT_PIN = "0.21.4"


def _render_wxt_config(project_name: str, purpose: str) -> str:
    return (
        "import { defineConfig } from 'wxt';\n\n"
        "export default defineConfig({\n"
        "  manifest: {\n"
        f"    name: {json.dumps(project_name, ensure_ascii=False)},\n"
        f"    description: {json.dumps(purpose, ensure_ascii=False)},\n"
        '    version: "0.1.0",\n'
        "  },\n"
        "});\n"
    )


def _render_background() -> str:
    return (
        "export default defineBackground(() => {\n"
        "  console.log('wxt extension scaffold ready');\n"
        "});\n"
    )


def _render_popup_html() -> str:
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        "  <title>Extension scaffold</title>\n"
        "</head>\n"
        "<body>\n"
        "  <main>Project scaffold ready.</main>\n"
        "</body>\n"
        "</html>\n"
    )


def _render_tsconfig() -> str:
    return '{\n  "extends": "./.wxt/tsconfig.json"\n}\n'


def _render_smoke_test() -> str:
    return (
        'import test from "node:test";\n'
        'import assert from "node:assert/strict";\n'
        'import fs from "node:fs";\n\n'
        'test("wxt drawing files exist", () => {\n'
        '  assert.equal(fs.existsSync("wxt.config.ts"), true);\n'
        '  assert.equal(fs.existsSync("entrypoints/background.ts"), true);\n'
        '  assert.equal(fs.existsSync("entrypoints/popup.html"), true);\n'
        "});\n"
    )


def scaffold_npm_wxt_extension(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "npm-wxt-extension":
        raise RecipeError(f"Unsupported WXT scaffold recipe: {recipe}")
    project_root.mkdir(parents=True, exist_ok=False)
    scaffold = run_command([provider.executable, "init", "--yes"], project_root)
    package = {
        "name": _npm_package_name(project_name),
        "version": "0.1.0",
        "description": purpose,
        "private": True,
        "type": "module",
        "scripts": {
            "dev": "wxt",
            "build": "wxt build",
            "zip": "wxt zip",
            "postinstall": "wxt prepare",
            "test": "node --test tests/smoke.test.js",
        },
        "devDependencies": {"wxt": WXT_PIN},
    }
    _write_json(project_root / "package.json", package)
    (project_root / "wxt.config.ts").write_text(_render_wxt_config(project_name, purpose), encoding="utf-8")
    (project_root / "tsconfig.json").write_text(_render_tsconfig(), encoding="utf-8")
    entrypoints = project_root / "entrypoints"
    entrypoints.mkdir(parents=True, exist_ok=True)
    (entrypoints / "background.ts").write_text(_render_background(), encoding="utf-8")
    (entrypoints / "popup.html").write_text(_render_popup_html(), encoding="utf-8")
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
        layout={
            "config": "wxt.config.ts",
            "entrypoints": "entrypoints/",
            "tests": "tests/",
            "packaging": "package.json",
            "output": ".output/",
        },
    )
