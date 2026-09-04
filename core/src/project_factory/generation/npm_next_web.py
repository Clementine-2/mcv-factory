"""Next.js App Router body on the npm language root.

Pinned Next 15 + React 18, not observed latest 16. Dev server is not a gate.
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
from .npm_vite_react import REACT_DOM_PIN, REACT_DOM_TYPES_PIN, REACT_PIN, REACT_TYPES_PIN
from .npm_vite_web import TYPESCRIPT_PIN

NEXT_PIN = "15.2.4"


def _render_layout() -> str:
    return (
        "import type { ReactNode } from 'react';\n\n"
        "export default function RootLayout({ children }: { children: ReactNode }) {\n"
        "  return (\n"
        '    <html lang="en">\n'
        "      <body>{children}</body>\n"
        "    </html>\n"
        "  );\n"
        "}\n"
    )


def _render_page() -> str:
    return (
        "export default function Page() {\n"
        "  return <main>web ui scaffold ready</main>;\n"
        "}\n"
    )


def _render_next_config() -> str:
    return (
        "/** @type {import('next').NextConfig} */\n"
        "const nextConfig = { eslint: { ignoreDuringBuilds: true } };\n"
        "export default nextConfig;\n"
    )


def _render_tsconfig() -> str:
    return """{
  "compilerOptions": {
    "target": "ES2017",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx"],
  "exclude": ["node_modules"]
}
"""


def _render_hello_route() -> str:
    return """// 示例 API 路由：GET /api/hello?name=X 返回 JSON。
// Next.js 路由文件只允许导出 HTTP 方法处理器，因此 buildHello 保持模块私有，
// 由导出的 GET 处理器调用；测试直接断言 GET 的行为。
interface HelloMessage {
  message: string;
}

function buildHello(name: string): HelloMessage {
  const who = name.trim() || 'world';
  return { message: `Hello, ${who}!` };
}

export async function GET(request: Request): Promise<Response> {
  const url = new URL(request.url);
  const name = url.searchParams.get('name') ?? 'world';
  return Response.json(buildHello(name));
}
"""


def _render_next_env() -> str:
    return '/// <reference types="next" />\n/// <reference types="next/image-types/global" />\n'


def _render_hello_test() -> str:
    return (
        'import test from "node:test";\n'
        'import assert from "node:assert/strict";\n'
        'import { GET } from "../app/api/hello/route.ts";\n\n'
        'test("GET /api/hello returns JSON for a named query param", async () => {\n'
        '  const response = await GET(new Request("http://localhost/api/hello?name=Ada"));\n'
        "  assert.equal(response.status, 200);\n"
        '  assert.deepEqual(await response.json(), { message: "Hello, Ada!" });\n'
        "});\n\n"
        'test("GET /api/hello defaults the name to world", async () => {\n'
        '  const response = await GET(new Request("http://localhost/api/hello"));\n'
        '  assert.deepEqual(await response.json(), { message: "Hello, world!" });\n'
        "});\n\n"
        'test("GET /api/hello trims whitespace around the name", async () => {\n'
        '  const response = await GET(new Request("http://localhost/api/hello?name=++"));\n'
        '  assert.deepEqual(await response.json(), { message: "Hello, world!" });\n'
        "});\n"
    )


def _render_smoke_test() -> str:
    return (
        'import test from "node:test";\n'
        'import assert from "node:assert/strict";\n'
        'import fs from "node:fs";\n\n'
        'test("next drawing files exist", () => {\n'
        '  assert.equal(fs.existsSync("app/page.tsx"), true);\n'
        '  assert.equal(fs.existsSync("app/layout.tsx"), true);\n'
        '  assert.equal(fs.existsSync("app/api/hello/route.ts"), true);\n'
        "  const pkg = JSON.parse(fs.readFileSync(\"package.json\", \"utf8\"));\n"
        f'  assert.equal(pkg.dependencies.next, "{NEXT_PIN}");\n'
        f'  assert.equal(pkg.dependencies.react, "{REACT_PIN}");\n'
        "});\n"
    )


def scaffold_npm_next_web(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "npm-next-web":
        raise RecipeError(f"Unsupported Next scaffold recipe: {recipe}")
    project_root.mkdir(parents=True, exist_ok=False)
    scaffold = run_command([provider.executable, "init", "--yes"], project_root)
    package = {
        "name": _npm_package_name(project_name),
        "version": "0.1.0",
        "description": purpose,
        "private": True,
        "scripts": {
            "dev": "next dev",
            "build": "next build",
            "start": "next start",
            "test": "node --test \"tests/*.test.js\"",
        },
        "dependencies": {
            "next": NEXT_PIN,
            "react": REACT_PIN,
            "react-dom": REACT_DOM_PIN,
        },
        "devDependencies": {
            "@types/node": "20.17.10",
            "@types/react": REACT_TYPES_PIN,
            "@types/react-dom": REACT_DOM_TYPES_PIN,
            "typescript": TYPESCRIPT_PIN,
        },
    }
    _write_json(project_root / "package.json", package)
    (project_root / "next.config.mjs").write_text(_render_next_config(), encoding="utf-8")
    (project_root / "tsconfig.json").write_text(_render_tsconfig(), encoding="utf-8")
    (project_root / "next-env.d.ts").write_text(_render_next_env(), encoding="utf-8")
    app = project_root / "app"
    app.mkdir(parents=True, exist_ok=True)
    (app / "layout.tsx").write_text(_render_layout(), encoding="utf-8")
    (app / "page.tsx").write_text(_render_page(), encoding="utf-8")
    api_hello = app / "api" / "hello"
    api_hello.mkdir(parents=True, exist_ok=True)
    (api_hello / "route.ts").write_text(_render_hello_route(), encoding="utf-8")
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "smoke.test.js").write_text(_render_smoke_test(), encoding="utf-8")
    (tests / "hello.test.js").write_text(_render_hello_test(), encoding="utf-8")
    run_command(
        [provider.executable, "install", "--no-fund", "--no-audit"],
        project_root,
        timeout=600,
    )
    return ScaffoldResult(
        command_result=scaffold,
        layout={
            "app": "app/",
            "entry": "app/page.tsx",
            "tests": "tests/",
            "packaging": "package.json",
            "output": ".next/",
        },
    )
