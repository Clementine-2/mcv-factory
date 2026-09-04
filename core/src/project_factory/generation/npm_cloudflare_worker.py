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
        "// 示例纯函数：拼接问候语，可被测试直接断言。\n"
        "export function buildGreeting(name) {\n"
        "  const who = name && name.trim() ? name.trim() : 'world';\n"
        "  return `Hello, ${who}!`;\n"
        "}\n\n"
        "export default {\n"
        "  async fetch(request) {\n"
        "    const url = new URL(request ? request.url : 'http://127.0.0.1/');\n"
        "    // 示例 endpoint：GET /health 返回 JSON 状态。\n"
        "    if (url.pathname === '/health') {\n"
        "      return new Response(JSON.stringify({ status: 'ok', service: scaffoldStatus() }), {\n"
        "        headers: { 'content-type': 'application/json' },\n"
        "      });\n"
        "    }\n"
        "    // 示例 endpoint：GET /?name=X 返回问候语文本。\n"
        "    const name = url.searchParams.get('name');\n"
        "    if (name) {\n"
        "      return new Response(buildGreeting(name), {\n"
        "        headers: { 'content-type': 'text/plain; charset=utf-8' },\n"
        "      });\n"
        "    }\n"
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


def _render_worker_test() -> str:
    return (
        'import test from "node:test";\n'
        'import assert from "node:assert/strict";\n'
        'import worker, { buildGreeting } from "../src/index.js";\n\n'
        'test("health endpoint returns json status", async () => {\n'
        '  const response = await worker.fetch(new Request("http://127.0.0.1/health"));\n'
        "  assert.equal(response.status, 200);\n"
        "  const body = await response.json();\n"
        '  assert.equal(body.status, "ok");\n'
        '  assert.equal(body.service, "worker scaffold ready");\n'
        "});\n\n"
        'test("root endpoint greets a named visitor", async () => {\n'
        '  const response = await worker.fetch(new Request("http://127.0.0.1/?name=Ada"));\n'
        '  assert.equal(await response.text(), "Hello, Ada!");\n'
        "});\n\n"
        'test("buildGreeting trims whitespace and defaults", () => {\n'
        '  assert.equal(buildGreeting("  Ada  "), "Hello, Ada!");\n'
        '  assert.equal(buildGreeting(""), "Hello, world!");\n'
        '  assert.equal(buildGreeting(null), "Hello, world!");\n'
        "});\n"
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
        "scripts": {"test": "node --test \"tests/*.test.js\""},
    }
    _write_json(project_root / "package.json", package)
    (project_root / "wrangler.toml").write_text(_render_wrangler(project_name), encoding="utf-8")
    source = project_root / "src"
    source.mkdir(parents=True, exist_ok=True)
    (source / "index.js").write_text(_render_worker(), encoding="utf-8")
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "smoke.test.js").write_text(_render_smoke_test(), encoding="utf-8")
    (tests / "worker.test.js").write_text(_render_worker_test(), encoding="utf-8")
    run_command([provider.executable, "install", "--no-fund", "--no-audit"], project_root, timeout=600)
    return ScaffoldResult(
        command_result=scaffold,
        layout={"source": "src/", "config": "wrangler.toml", "packaging": "package.json"},
    )
