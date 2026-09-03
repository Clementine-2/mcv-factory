"""Commander CLI on the npm language root. argparse/clap stay on their language roots."""

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

COMMANDER_PIN = "12.1.0"
TYPES_NODE_PIN = "22.13.10"


def _render_cli() -> str:
    return (
        "import { Command } from 'commander';\n\n"
        "export const VERSION = '0.1.0';\n\n"
        "export function buildProgram(): Command {\n"
        "  const program = new Command();\n"
        "  program.name('scaffold-cli').version(VERSION).description('CLI scaffold ready');\n"
        "  program.action(() => {\n"
        "    console.log('Project scaffold ready. Implement domain behavior through the coding-agent workflow.');\n"
        "  });\n"
        "  program.exitOverride();\n"
        "  return program;\n"
        "}\n\n"
        "export function run(argv: string[] = process.argv): void {\n"
        "  buildProgram().parse(argv);\n"
        "}\n\n"
        "if (process.argv[1] && process.argv[1].endsWith('cli.js')) {\n"
        "  run();\n"
        "}\n"
    )


def _render_tsconfig() -> str:
    return """{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "strict": true,
    "declaration": true,
    "outDir": "dist",
    "rootDir": "src",
    "skipLibCheck": true
  },
  "include": ["src"]
}
"""


def _render_smoke_test() -> str:
    return (
        'import test from "node:test";\n'
        'import assert from "node:assert/strict";\n'
        'import { buildProgram, VERSION } from "../dist/cli.js";\n\n'
        'test("commander version is defined", () => {\n'
        '  assert.equal(VERSION, "0.1.0");\n'
        "});\n\n"
        'test("default action prints scaffold status", () => {\n'
        "  const program = buildProgram();\n"
        "  const lines = [];\n"
        "  const original = console.log;\n"
        "  console.log = (message) => { lines.push(String(message)); };\n"
        "  try {\n"
        '    program.parse(["node", "cli"], { from: "user" });\n'
        "  } finally {\n"
        "    console.log = original;\n"
        "  }\n"
        '  assert.equal(lines.some((line) => line.includes("Project scaffold ready")), true);\n'
        "});\n"
    )


def scaffold_npm_commander_cli(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "npm-commander-cli":
        raise RecipeError(f"Unsupported Commander scaffold recipe: {recipe}")
    project_root.mkdir(parents=True, exist_ok=False)
    scaffold = run_command([provider.executable, "init", "--yes"], project_root)
    package = {
        "name": _npm_package_name(project_name),
        "version": "0.1.0",
        "description": purpose,
        "private": True,
        "type": "module",
        "bin": {"scaffold-cli": "./dist/cli.js"},
        "scripts": {"build": "tsc", "test": "tsc && node --test tests/smoke.test.js"},
        "dependencies": {"commander": COMMANDER_PIN},
        "devDependencies": {"@types/node": TYPES_NODE_PIN, "typescript": TYPESCRIPT_PIN},
    }
    _write_json(project_root / "package.json", package)
    (project_root / "tsconfig.json").write_text(_render_tsconfig(), encoding="utf-8")
    source = project_root / "src"
    source.mkdir(parents=True, exist_ok=True)
    (source / "cli.ts").write_text(_render_cli(), encoding="utf-8")
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "smoke.test.js").write_text(_render_smoke_test(), encoding="utf-8")
    run_command([provider.executable, "install", "--no-fund", "--no-audit"], project_root, timeout=600)
    return ScaffoldResult(
        command_result=scaffold,
        layout={"source": "src/", "cli": "src/cli.ts", "packaging": "package.json"},
    )
