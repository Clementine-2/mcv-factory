"""Cloudflare Worker on the npm language root.

wrangler deploy is not a verification gate. The factory does not install a
Cloudflare account or ship wrangler as a required runtime.
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


def _render_worker() -> str:
    return (
        "export function scaffoldStatus() {\n"
        '  return "worker scaffold ready";\n'
        "}\n\n"
        "export default {\n"
        "  async fetch() {\n"
        "    return new Response(scaffoldStatus());\n"
        "  },\n"
        "};\n"
    )


def _render_wrangler(project_name: str) -> str:
    name = json.dumps(project_name, ensure_ascii=False)
    return (
        f"name = {name}\n"
        'main = "src/index.js"\n'
        'compatibility_date = "2025-03-20"\n'
    )


def _render_smoke_test() -> str:
    return (
        'import test from "node:test";\n'
        'import assert from "node:assert/strict";\n'
        'import fs from "node:fs";\n'
        'import worker, { scaffoldStatus } from "../src/index.js";\n\n'
        'test("worker drawing files exist", () => {\n'
        '  assert.equal(fs.existsSync("wrangler.toml"), true);\n'
        '  assert.equal(scaffoldStatus(), "worker scaffold ready");\n'
        "});\n\n"
        'test("fetch returns scaffold status", async () => {\n'
        "  const response = await worker.fetch();\n"
        '  assert.equal(await response.text(), "worker scaffold ready");\n'
        "});\n"
    )


def scaffold_npm_cloudflare_worker(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "npm-cloudflare-worker":
        raise RecipeError(f"Unsupported Cloudflare Worker scaffold recipe: {recipe}")
    project_root.mkdir(parents=True, exist_ok=False)
    scaffold = run_command([provider.executable, "init", "--yes"], project_root)
    package = {
        "name": _npm_package_name(project_name),
        "version": "0.1.0",
        "description": purpose,
        "private": True,
        "type": "module",
        "scripts": {"test": "node --test tests/smoke.test.js"},
    }
    _write_json(project_root / "package.json", package)
    (project_root / "wrangler.toml").write_text(_render_wrangler(project_name), encoding="utf-8")
    source = project_root / "src"
    source.mkdir(parents=True, exist_ok=True)
    (source / "index.js").write_text(_render_worker(), encoding="utf-8")
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "smoke.test.js").write_text(_render_smoke_test(), encoding="utf-8")
    run_command([provider.executable, "install", "--no-fund", "--no-audit"], project_root, timeout=600)
    return ScaffoldResult(
        command_result=scaffold,
        layout={"source": "src/", "config": "wrangler.toml", "packaging": "package.json"},
    )
