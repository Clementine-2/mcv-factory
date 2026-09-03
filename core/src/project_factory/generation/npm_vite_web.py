"""TypeScript web UI on the npm language root, Vite body.

Vanilla TypeScript, not React/Next. Those are body swaps, not new kinds.
Versions are pinned; observed latest is not auto-promoted.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from ..recipes import (
    ProviderView,
    RecipeError,
    ScaffoldResult,
    _npm_package_name,
    _write_json,
    run_command,
)

VITE_PIN = "6.3.5"
TYPESCRIPT_PIN = "5.8.3"
PLAYWRIGHT_PIN = "1.49.1"


def render_playwright_config() -> str:
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
    command: 'npx vite preview --host 127.0.0.1 --port 4173',
    url: 'http://127.0.0.1:4173',
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
"""


def render_playwright_e2e() -> str:
    return """import { test, expect } from '@playwright/test';

test('page shows scaffold status in a real browser', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('#app')).toContainText('web ui scaffold ready');
});
"""


def attach_playwright(package: dict, project_root: Path) -> None:
    package.setdefault("scripts", {})["test:e2e"] = "playwright test"
    package.setdefault("devDependencies", {})["@playwright/test"] = PLAYWRIGHT_PIN
    (project_root / "playwright.config.ts").write_text(render_playwright_config(), encoding="utf-8")
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "e2e.spec.js").write_text(render_playwright_e2e(), encoding="utf-8")


def playwright_install_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD"] = "1"
    return env


def _render_index_html(project_name: str) -> str:
    title = json.dumps(project_name, ensure_ascii=False)
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"  <title>{title[1:-1]}</title>\n"
        "</head>\n"
        "<body>\n"
        '  <div id="app"></div>\n'
        '  <script type="module" src="/src/main.ts"></script>\n'
        "</body>\n"
        "</html>\n"
    )


def _render_main() -> str:
    return (
        'export function scaffoldStatus(): string {\n'
        '  return "web ui scaffold ready";\n'
        "}\n\n"
        "const root = document.querySelector(\"#app\");\n"
        "if (root) {\n"
        "  root.textContent = scaffoldStatus();\n"
        "}\n"
    )


def _render_vite_config() -> str:
    return "import { defineConfig } from 'vite';\n\nexport default defineConfig({});\n"


def _render_tsconfig() -> str:
    return """{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "noEmit": true,
    "skipLibCheck": true,
    "lib": ["ES2022", "DOM"]
  },
  "include": ["src"]
}
"""


def _render_env_dts() -> str:
    return "/// <reference types=\"vite/client\" />\n"


def _render_smoke_test() -> str:
    return (
        'import test from "node:test";\n'
        'import assert from "node:assert/strict";\n'
        'import fs from "node:fs";\n\n'
        'test("vite drawing files exist", () => {\n'
        '  assert.equal(fs.existsSync("index.html"), true);\n'
        '  assert.equal(fs.existsSync("src/main.ts"), true);\n'
        '  assert.equal(fs.existsSync("vite.config.ts"), true);\n'
        "});\n"
    )


def scaffold_npm_vite_web(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "npm-vite-web":
        raise RecipeError(f"Unsupported Vite web scaffold recipe: {recipe}")
    project_root.mkdir(parents=True, exist_ok=False)
    scaffold = run_command([provider.executable, "init", "--yes"], project_root)
    package = {
        "name": _npm_package_name(project_name),
        "version": "0.1.0",
        "description": purpose,
        "private": True,
        "type": "module",
        "scripts": {
            "dev": "vite",
            "build": "vite build",
            "preview": "vite preview",
            "test": "node --test tests/smoke.test.js",
        },
        "devDependencies": {
            "typescript": TYPESCRIPT_PIN,
            "vite": VITE_PIN,
        },
    }
    (project_root / "index.html").write_text(_render_index_html(project_name), encoding="utf-8")
    (project_root / "vite.config.ts").write_text(_render_vite_config(), encoding="utf-8")
    (project_root / "tsconfig.json").write_text(_render_tsconfig(), encoding="utf-8")
    source = project_root / "src"
    source.mkdir(parents=True, exist_ok=True)
    (source / "main.ts").write_text(_render_main(), encoding="utf-8")
    (source / "vite-env.d.ts").write_text(_render_env_dts(), encoding="utf-8")
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "smoke.test.js").write_text(_render_smoke_test(), encoding="utf-8")
    attach_playwright(package, project_root)
    _write_json(project_root / "package.json", package)
    run_command(
        [provider.executable, "install", "--no-fund", "--no-audit"],
        project_root,
        timeout=600,
        env=playwright_install_env(),
    )
    return ScaffoldResult(
        command_result=scaffold,
        layout={
            "source": "src/",
            "entry": "index.html",
            "tests": "tests/",
            "packaging": "package.json",
            "output": "dist/",
        },
    )
