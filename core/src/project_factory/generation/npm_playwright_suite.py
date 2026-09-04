"""Standalone Playwright test-suite on the npm language root.

True-browser VERIFIED only when Playwright launches a system browser.
Browsers are not downloaded by the factory.
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
from .npm_vite_web import PLAYWRIGHT_PIN, playwright_install_env


def _render_config() -> str:
    return """import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  testMatch: 'e2e.spec.js',
  fullyParallel: false,
  timeout: 30_000,
  use: {
    baseURL: 'http://127.0.0.1:4173',
    channel: process.platform === 'win32' ? 'msedge' : 'chrome',
    headless: true,
  },
  webServer: {
    command: 'node scripts/serve.mjs',
    url: 'http://127.0.0.1:4173',
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
"""


def _render_serve() -> str:
    return (
        "import http from 'node:http';\n"
        "import fs from 'node:fs';\n"
        "import path from 'node:path';\n\n"
        "const html = fs.readFileSync(path.join('fixtures', 'index.html'));\n"
        "http.createServer((request, response) => {\n"
        "  response.writeHead(200, { 'content-type': 'text/html; charset=utf-8' });\n"
        "  response.end(html);\n"
        "}).listen(4173, '127.0.0.1');\n"
    )


def _render_fixture() -> str:
    return (
        "<!doctype html>\n"
        "<html lang=\"en\">\n"
        "<head><meta charset=\"utf-8\"><title>Playwright suite</title></head>\n"
        "<body>\n"
        "  <main id=\"app\">\n"
        '    <p id="status">test suite scaffold ready</p>\n'
        '    <button id="counter" type="button">Count: 0</button>\n'
        "  </main>\n"
        "  <script>\n"
        "    // 示例交互：点击按钮让计数器 +1，供 e2e 测试断言。\n"
        "    const button = document.getElementById('counter');\n"
        "    let count = 0;\n"
        "    button.addEventListener('click', () => {\n"
        "      count += 1;\n"
        "      button.textContent = `Count: ${count}`;\n"
        "    });\n"
        "  </script>\n"
        "</body>\n"
        "</html>\n"
    )


def _render_e2e() -> str:
    return (
        "import { test, expect } from '@playwright/test';\n\n"
        "test('fixture page shows scaffold status in a real browser', async ({ page }) => {\n"
        "  await page.goto('/');\n"
        "  await expect(page.locator('#app')).toContainText('test suite scaffold ready');\n"
        "});\n\n"
        "// 示例 e2e：验证可交互的计数器在真实浏览器中工作。\n"
        "test('counter increments on click in a real browser', async ({ page }) => {\n"
        "  await page.goto('/');\n"
        "  const button = page.locator('#counter');\n"
        "  await expect(button).toHaveText('Count: 0');\n"
        "  await button.click();\n"
        "  await expect(button).toHaveText('Count: 1');\n"
        "  await button.click();\n"
        "  await button.click();\n"
        "  await expect(button).toHaveText('Count: 3');\n"
        "});\n"
    )


def _render_readme() -> str:
    return (
        "# Playwright Test Suite\n\n"
        "一个独立可运行的 Playwright 示例测试套件。\n\n"
        "## 运行方式\n\n"
        "```bash\n"
        "npm install          # 安装 @playwright/test\n"
        "npx playwright install --with-deps   # 可选：安装浏览器（已装则可跳过）\n"
        "npm run test:e2e     # 启动本地静态服务器并运行浏览器 e2e 测试\n"
        "```\n\n"
        "## 结构说明\n\n"
        "- `fixtures/index.html`：被测的示例页面，内含一个可交互计数器。\n"
        "- `tests/e2e.spec.js`：示例 e2e 测试，断言页面状态与计数器点击行为。\n"
        "- `scripts/serve.mjs`：启动本地静态服务器（127.0.0.1:4173）。\n"
        "- `playwright.config.ts`：Playwright 配置，自动起停本地服务器。\n\n"
        "浏览器下载由工厂显式跳过（`PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1`）；\n"
        "本机跑 e2e 前请先安装浏览器：`npx playwright install`。\n"
    )


def _render_smoke_test() -> str:
    return (
        'import test from "node:test";\n'
        'import assert from "node:assert/strict";\n'
        'import fs from "node:fs";\n\n'
        'test("playwright suite drawing files exist", () => {\n'
        '  assert.equal(fs.existsSync("playwright.config.ts"), true);\n'
        '  assert.equal(fs.existsSync("fixtures/index.html"), true);\n'
        '  assert.equal(fs.existsSync("tests/e2e.spec.js"), true);\n'
        "  const pkg = JSON.parse(fs.readFileSync(\"package.json\", \"utf8\"));\n"
        f'  assert.equal(pkg.devDependencies["@playwright/test"], "{PLAYWRIGHT_PIN}");\n'
        "});\n"
    )


def scaffold_npm_playwright_suite(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "npm-playwright-suite":
        raise RecipeError(f"Unsupported Playwright suite scaffold recipe: {recipe}")
    project_root.mkdir(parents=True, exist_ok=False)
    scaffold = run_command([provider.executable, "init", "--yes"], project_root)
    package = {
        "name": _npm_package_name(project_name),
        "version": "0.1.0",
        "description": purpose,
        "private": True,
        "type": "module",
        "scripts": {
            "test": "node --test \"tests/*.test.js\"",
            "test:e2e": "playwright test",
        },
        "devDependencies": {"@playwright/test": PLAYWRIGHT_PIN},
    }
    _write_json(project_root / "package.json", package)
    (project_root / "playwright.config.ts").write_text(_render_config(), encoding="utf-8")
    (project_root / "README.md").write_text(_render_readme(), encoding="utf-8")
    scripts = project_root / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    (scripts / "serve.mjs").write_text(_render_serve(), encoding="utf-8")
    fixtures = project_root / "fixtures"
    fixtures.mkdir(parents=True, exist_ok=True)
    (fixtures / "index.html").write_text(_render_fixture(), encoding="utf-8")
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "e2e.spec.js").write_text(_render_e2e(), encoding="utf-8")
    (tests / "smoke.test.js").write_text(_render_smoke_test(), encoding="utf-8")
    run_command(
        [provider.executable, "install", "--no-fund", "--no-audit"],
        project_root,
        timeout=600,
        env=playwright_install_env(),
    )
    return ScaffoldResult(
        command_result=scaffold,
        layout={
            "tests": "tests/",
            "fixtures": "fixtures/",
            "config": "playwright.config.ts",
            "packaging": "package.json",
        },
    )
