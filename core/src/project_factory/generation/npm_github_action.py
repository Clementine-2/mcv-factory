"""GitHub Action on the npm language root.

Does not run on GitHub-hosted runners. Node 20 entry is compiled locally.
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
from .npm_vite_web import TYPESCRIPT_PIN

ACTIONS_CORE_PIN = "1.11.1"


def _render_logic() -> str:
    return """// 示例 action 逻辑：纯函数，可在 Node 中直接测试。
export interface Summary {
  count: number;
  sum: number;
  average: number;
}

export function summarize(values: number[]): Summary {
  const count = values.length;
  const sum = values.reduce((acc, value) => acc + value, 0);
  const average = count === 0 ? 0 : sum / count;
  return { count, sum, average };
}

export function parseNumbers(raw: string): number[] {
  return raw
    .split(',')
    .map((part) => Number(part.trim()))
    .filter((value) => Number.isFinite(value));
}
"""


def _render_status() -> str:
    return (
        "export function scaffoldStatus(): string {\n"
        '  return "github action scaffold ready";\n'
        "}\n"
    )


def _render_index() -> str:
    return (
        "import * as core from '@actions/core';\n"
        "import { scaffoldStatus } from './status';\n"
        "import { parseNumbers, summarize } from './logic';\n\n"
        "core.setOutput('status', scaffoldStatus());\n\n"
        "// 示例逻辑：把逗号分隔的 numbers 输入汇总后写入 outputs。\n"
        "const raw = core.getInput('numbers', { required: false });\n"
        "const summary = summarize(parseNumbers(raw));\n"
        "core.setOutput('count', String(summary.count));\n"
        "core.setOutput('sum', String(summary.sum));\n"
        "core.setOutput('average', String(summary.average));\n"
    )


def _render_action_yml(project_name: str, purpose: str) -> str:
    return (
        f"name: {json.dumps(project_name, ensure_ascii=False)}\n"
        f"description: {json.dumps(purpose, ensure_ascii=False)}\n"
        "inputs:\n"
        "  numbers:\n"
        "    description: Comma-separated numbers to summarize\n"
        "    required: false\n"
        "runs:\n"
        "  using: node20\n"
        "  main: dist/index.js\n"
        "outputs:\n"
        "  status:\n"
        "    description: Scaffold status string\n"
        "  count:\n"
        "    description: Count of parsed numbers\n"
        "  sum:\n"
        "    description: Sum of parsed numbers\n"
        "  average:\n"
        "    description: Average of parsed numbers\n"
    )


def _render_tsconfig() -> str:
    return """{
  "compilerOptions": {
    "target": "ES2022",
    "module": "commonjs",
    "moduleResolution": "node",
    "strict": true,
    "esModuleInterop": true,
    "outDir": "dist",
    "rootDir": "src",
    "skipLibCheck": true
  },
  "include": ["src"]
}
"""


def _render_logic_test() -> str:
    return (
        'const test = require("node:test");\n'
        'const assert = require("node:assert/strict");\n'
        'const { parseNumbers, summarize } = require("../dist/logic.js");\n\n'
        'test("summarize computes count, sum and average", () => {\n'
        '  assert.deepEqual(summarize([1, 2, 3, 4]), { count: 4, sum: 10, average: 2.5 });\n'
        "});\n\n"
        'test("summarize handles an empty list", () => {\n'
        '  assert.deepEqual(summarize([]), { count: 0, sum: 0, average: 0 });\n'
        "});\n\n"
        'test("parseNumbers splits and filters a csv string", () => {\n'
        '  assert.deepEqual(parseNumbers("1, 2, 3"), [1, 2, 3]);\n'
        '  assert.deepEqual(parseNumbers("1,oops,3"), [1, 3]);\n'
        "});\n"
    )


def _render_smoke_test() -> str:
    return (
        'const test = require("node:test");\n'
        'const assert = require("node:assert/strict");\n'
        'const fs = require("node:fs");\n'
        'const { scaffoldStatus } = require("../dist/status.js");\n\n'
        'test("action compiles and status is defined", () => {\n'
        '  assert.equal(fs.existsSync("action.yml"), true);\n'
        '  assert.equal(scaffoldStatus(), "github action scaffold ready");\n'
        "});\n"
    )


def scaffold_npm_github_action(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "npm-github-action":
        raise RecipeError(f"Unsupported GitHub Action scaffold recipe: {recipe}")
    project_root.mkdir(parents=True, exist_ok=False)
    scaffold = run_command([provider.executable, "init", "--yes"], project_root)
    package = {
        "name": _npm_package_name(project_name),
        "version": "0.1.0",
        "description": purpose,
        "private": True,
        "main": "./dist/index.js",
        "scripts": {
            "build": "tsc",
            "test": "tsc && node --test \"tests/*.test.js\"",
        },
        "dependencies": {"@actions/core": ACTIONS_CORE_PIN},
        "devDependencies": {"typescript": TYPESCRIPT_PIN},
    }
    _write_json(project_root / "package.json", package)
    (project_root / "action.yml").write_text(_render_action_yml(project_name, purpose), encoding="utf-8")
    (project_root / "tsconfig.json").write_text(_render_tsconfig(), encoding="utf-8")
    source = project_root / "src"
    source.mkdir(parents=True, exist_ok=True)
    (source / "status.ts").write_text(_render_status(), encoding="utf-8")
    (source / "logic.ts").write_text(_render_logic(), encoding="utf-8")
    (source / "index.ts").write_text(_render_index(), encoding="utf-8")
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "smoke.test.js").write_text(_render_smoke_test(), encoding="utf-8")
    (tests / "logic.test.js").write_text(_render_logic_test(), encoding="utf-8")
    run_command(
        [provider.executable, "install", "--no-fund", "--no-audit"],
        project_root,
        timeout=600,
    )
    return ScaffoldResult(
        command_result=scaffold,
        layout={"source": "src/", "action": "action.yml", "tests": "tests/", "packaging": "package.json"},
    )
