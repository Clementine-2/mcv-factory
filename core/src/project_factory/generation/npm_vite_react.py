"""React body on the existing TypeScript Vite web line.

This is a body swap, not a new work-product kind. Pins are tested versions,
not npm observed latest.
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
from .npm_vite_web import TYPESCRIPT_PIN, VITE_PIN, attach_playwright, playwright_install_env

REACT_PIN = "18.3.1"
REACT_DOM_PIN = "18.3.1"
REACT_TYPES_PIN = "18.3.18"
REACT_DOM_TYPES_PIN = "18.3.5"
PLUGIN_REACT_PIN = "4.5.2"


def _render_index_html(project_name: str) -> str:
    title = json.dumps(project_name, ensure_ascii=False)[1:-1]
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"  <title>{title}</title>\n"
        "</head>\n"
        "<body>\n"
        '  <div id="app"></div>\n'
        '  <script type="module" src="/src/main.tsx"></script>\n'
        "</body>\n"
        "</html>\n"
    )


def _render_vite_config() -> str:
    return (
        "import { defineConfig } from 'vite';\n"
        "import react from '@vitejs/plugin-react';\n\n"
        "export default defineConfig({\n"
        "  plugins: [react()],\n"
        "});\n"
    )


def _render_tsconfig() -> str:
    return """{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noEmit": true,
    "skipLibCheck": true,
    "lib": ["ES2022", "DOM"]
  },
  "include": ["src"]
}
"""


def _render_app() -> str:
    return (
        "export function scaffoldStatus(): string {\n"
        '  return "web ui scaffold ready";\n'
        "}\n\n"
        "export function App() {\n"
        "  return <main>{scaffoldStatus()}</main>;\n"
        "}\n"
    )


def _render_main() -> str:
    return (
        "import { createRoot } from 'react-dom/client';\n"
        "import { App } from './App';\n\n"
        "const root = document.querySelector('#app');\n"
        "if (root) {\n"
        "  createRoot(root).render(<App />);\n"
        "}\n"
    )


def _render_env_dts() -> str:
    return '/// <reference types="vite/client" />\n'


def _render_smoke_test() -> str:
    return (
        'import test from "node:test";\n'
        'import assert from "node:assert/strict";\n'
        'import fs from "node:fs";\n\n'
        'test("react vite drawing files exist", () => {\n'
        '  assert.equal(fs.existsSync("src/App.tsx"), true);\n'
        '  assert.equal(fs.existsSync("src/main.tsx"), true);\n'
        '  assert.equal(fs.existsSync("vite.config.ts"), true);\n'
        "  const pkg = JSON.parse(fs.readFileSync(\"package.json\", \"utf8\"));\n"
        f'  assert.equal(pkg.dependencies.react, "{REACT_PIN}");\n'
        "});\n"
    )


def scaffold_npm_vite_react(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "npm-vite-react":
        raise RecipeError(f"Unsupported Vite React scaffold recipe: {recipe}")
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
        "dependencies": {
            "react": REACT_PIN,
            "react-dom": REACT_DOM_PIN,
        },
        "devDependencies": {
            "@types/react": REACT_TYPES_PIN,
            "@types/react-dom": REACT_DOM_TYPES_PIN,
            "@vitejs/plugin-react": PLUGIN_REACT_PIN,
            "typescript": TYPESCRIPT_PIN,
            "vite": VITE_PIN,
        },
    }
    (project_root / "index.html").write_text(_render_index_html(project_name), encoding="utf-8")
    (project_root / "vite.config.ts").write_text(_render_vite_config(), encoding="utf-8")
    (project_root / "tsconfig.json").write_text(_render_tsconfig(), encoding="utf-8")
    source = project_root / "src"
    source.mkdir(parents=True, exist_ok=True)
    (source / "App.tsx").write_text(_render_app(), encoding="utf-8")
    (source / "main.tsx").write_text(_render_main(), encoding="utf-8")
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
            "app": "src/App.tsx",
            "tests": "tests/",
            "packaging": "package.json",
            "output": "dist/",
        },
    )
