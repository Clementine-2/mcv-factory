"""Vue body on the existing TypeScript Vite web line.

This is a body swap, not a new work-product kind. Pins are tested versions.
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
from .npm_vite_web import TYPESCRIPT_PIN, VITE_PIN, attach_playwright, playwright_install_env

VUE_PIN = "3.5.13"
PLUGIN_VUE_PIN = "5.2.1"


def _render_index_html(project_name: str) -> str:
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"  <title>{project_name}</title>\n"
        "</head>\n"
        "<body>\n"
        '  <div id="app"></div>\n'
        '  <script type="module" src="/src/main.ts"></script>\n'
        "</body>\n"
        "</html>\n"
    )


def _render_vite_config() -> str:
    return (
        "import { defineConfig } from 'vite';\n"
        "import vue from '@vitejs/plugin-vue';\n\n"
        "export default defineConfig({\n"
        "  plugins: [vue()],\n"
        "});\n"
    )


def _render_tsconfig() -> str:
    return """{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "noEmit": true,
    "skipLibCheck": true,
    "lib": ["ES2022", "DOM"],
    "jsx": "preserve"
  },
  "include": ["src"]
}
"""


def _render_env_dts() -> str:
    return (
        '/// <reference types="vite/client" />\n'
        "declare module '*.vue' {\n"
        "  import type { DefineComponent } from 'vue';\n"
        "  const component: DefineComponent<object, object, unknown>;\n"
        "  export default component;\n"
        "}\n"
    )


def _render_counter() -> str:
    return """// 示例功能：纯函数风格的计数器状态机，可被组件复用并在 Node 中直接测试。
export interface CounterState {
  count: number;
}

export function createCounter(initial: number = 0): CounterState {
  return { count: initial };
}

export function increment(state: CounterState): CounterState {
  return { count: state.count + 1 };
}

export function decrement(state: CounterState): CounterState {
  return { count: state.count - 1 };
}

export function formatCounter(state: CounterState): string {
  return `Count: ${state.count}`;
}
"""


def _render_app() -> str:
    return (
        '<script setup lang="ts">\n'
        "import { ref } from 'vue';\n"
        "import { createCounter, decrement, formatCounter, increment } from './counter';\n"
        "import type { CounterState } from './counter';\n\n"
        'const status = "web ui scaffold ready";\n'
        "// 示例页面组件：可交互计数器，按钮点击驱动 ./counter 里的纯函数。\n"
        "const state = ref<CounterState>(createCounter());\n\n"
        "function incrementCounter(): void {\n"
        "  state.value = increment(state.value);\n"
        "}\n\n"
        "function decrementCounter(): void {\n"
        "  state.value = decrement(state.value);\n"
        "}\n"
        "</script>\n\n"
        "<template>\n"
        "  <main>\n"
        "    <p>{{ status }}</p>\n"
        '    <p id="counter">{{ formatCounter(state) }}</p>\n'
        '    <button type="button" @click="decrementCounter()">-</button>\n'
        '    <button type="button" @click="incrementCounter()">+</button>\n'
        "  </main>\n"
        "</template>\n"
    )


def _render_main() -> str:
    return (
        "import { createApp } from 'vue';\n"
        "import App from './App.vue';\n\n"
        "createApp(App).mount('#app');\n"
    )


def _render_counter_test() -> str:
    return (
        'import test from "node:test";\n'
        'import assert from "node:assert/strict";\n'
        'import { createCounter, decrement, formatCounter, increment } from "../src/counter.ts";\n\n'
        'test("counter component starts at the initial value", () => {\n'
        '  assert.deepEqual(createCounter(), { count: 0 });\n'
        '  assert.deepEqual(createCounter(4), { count: 4 });\n'
        "});\n\n"
        'test("increment then decrement returns to start", () => {\n'
        "  let state = createCounter(2);\n"
        "  state = increment(state);\n"
        '  assert.equal(state.count, 3);\n'
        "  state = decrement(state);\n"
        '  assert.equal(state.count, 2);\n'
        "});\n\n"
        'test("formatCounter renders the label", () => {\n'
        '  assert.equal(formatCounter(createCounter(6)), "Count: 6");\n'
        "});\n"
    )


def _render_smoke_test() -> str:
    return (
        'import test from "node:test";\n'
        'import assert from "node:assert/strict";\n'
        'import fs from "node:fs";\n\n'
        'test("vue vite drawing files exist", () => {\n'
        '  assert.equal(fs.existsSync("src/App.vue"), true);\n'
        '  assert.equal(fs.existsSync("src/main.ts"), true);\n'
        '  assert.equal(fs.existsSync("vite.config.ts"), true);\n'
        "  const pkg = JSON.parse(fs.readFileSync(\"package.json\", \"utf8\"));\n"
        f'  assert.equal(pkg.dependencies.vue, "{VUE_PIN}");\n'
        "});\n"
    )


def scaffold_npm_vite_vue(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "npm-vite-vue":
        raise RecipeError(f"Unsupported Vite Vue scaffold recipe: {recipe}")
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
            "test": "node --test \"tests/*.test.js\"",
        },
        "dependencies": {"vue": VUE_PIN},
        "devDependencies": {
            "@vitejs/plugin-vue": PLUGIN_VUE_PIN,
            "typescript": TYPESCRIPT_PIN,
            "vite": VITE_PIN,
        },
    }
    (project_root / "index.html").write_text(_render_index_html(project_name), encoding="utf-8")
    (project_root / "vite.config.ts").write_text(_render_vite_config(), encoding="utf-8")
    (project_root / "tsconfig.json").write_text(_render_tsconfig(), encoding="utf-8")
    source = project_root / "src"
    source.mkdir(parents=True, exist_ok=True)
    (source / "App.vue").write_text(_render_app(), encoding="utf-8")
    (source / "counter.ts").write_text(_render_counter(), encoding="utf-8")
    (source / "main.ts").write_text(_render_main(), encoding="utf-8")
    (source / "vite-env.d.ts").write_text(_render_env_dts(), encoding="utf-8")
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "smoke.test.js").write_text(_render_smoke_test(), encoding="utf-8")
    (tests / "counter.test.js").write_text(_render_counter_test(), encoding="utf-8")
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
            "app": "src/App.vue",
            "tests": "tests/",
            "packaging": "package.json",
            "output": "dist/",
        },
    )
