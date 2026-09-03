"""VS Code extension on the npm language root.

Does not launch VS Code or publish to the Marketplace.
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
from .npm_vite_web import TYPESCRIPT_PIN

VSCE_PIN = "3.2.2"
VSCODE_TYPES_PIN = "1.96.0"


def _render_extension(command_id: str) -> str:
    return f"""import * as vscode from 'vscode';

export function activate(context: vscode.ExtensionContext): void {{
  context.subscriptions.push(
    vscode.commands.registerCommand({command_id!r}, () => {{
      void vscode.window.showInformationMessage('vscode extension scaffold ready');
    }}),
  );
}}

export function deactivate(): void {{}}
"""


def _render_tsconfig() -> str:
    return """{
  "compilerOptions": {
    "target": "ES2022",
    "module": "commonjs",
    "moduleResolution": "node",
    "strict": true,
    "outDir": "dist",
    "rootDir": "src",
    "skipLibCheck": true,
    "lib": ["ES2022"]
  },
  "include": ["src"]
}
"""


def _render_smoke_test() -> str:
    return (
        'const test = require("node:test");\n'
        'const assert = require("node:assert/strict");\n'
        'const fs = require("node:fs");\n\n'
        'test("vscode extension drawing files exist", () => {\n'
        '  assert.equal(fs.existsSync("src/extension.ts"), true);\n'
        '  const pkg = JSON.parse(fs.readFileSync("package.json", "utf8"));\n'
        '  assert.equal(pkg.engines.vscode, "^1.96.0");\n'
        '  assert.equal(typeof pkg.contributes.commands[0].command, "string");\n'
        "});\n"
    )


def scaffold_npm_vscode_extension(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "npm-vscode-extension":
        raise RecipeError(f"Unsupported VS Code extension scaffold recipe: {recipe}")
    npm_name = _npm_package_name(project_name)
    command_id = f"{npm_name}.hello"
    project_root.mkdir(parents=True, exist_ok=False)
    scaffold = run_command([provider.executable, "init", "--yes"], project_root)
    package = {
        "name": npm_name,
        "displayName": project_name,
        "description": purpose,
        "version": "0.1.0",
        "publisher": "factory-scaffold",
        "private": True,
        "engines": {"vscode": "^1.96.0"},
        "categories": ["Other"],
        "activationEvents": [f"onCommand:{command_id}"],
        "main": "./dist/extension.js",
        "contributes": {
            "commands": [{"command": command_id, "title": "Scaffold Hello"}],
        },
        "scripts": {
            "compile": "tsc -p .",
            "test": "tsc -p . && node --test tests/smoke.test.js",
            "package": "vsce package --allow-missing-repository --no-dependencies",
        },
        "devDependencies": {
            "@types/vscode": VSCODE_TYPES_PIN,
            "@vscode/vsce": VSCE_PIN,
            "typescript": TYPESCRIPT_PIN,
        },
    }
    _write_json(project_root / "package.json", package)
    (project_root / "tsconfig.json").write_text(_render_tsconfig(), encoding="utf-8")
    source = project_root / "src"
    source.mkdir(parents=True, exist_ok=True)
    (source / "extension.ts").write_text(_render_extension(command_id), encoding="utf-8")
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "smoke.test.js").write_text(_render_smoke_test(), encoding="utf-8")
    (project_root / ".vscodeignore").write_text("src/**\ntests/**\nnode_modules/**\n", encoding="utf-8")
    (project_root / "LICENSE").write_text("MIT License\n\nCopyright (c) factory-scaffold\n", encoding="utf-8")
    run_command(
        [provider.executable, "install", "--no-fund", "--no-audit"],
        project_root,
        timeout=600,
    )
    return ScaffoldResult(
        command_result=scaffold,
        layout={"source": "src/extension.ts", "tests": "tests/", "packaging": "package.json"},
    )
