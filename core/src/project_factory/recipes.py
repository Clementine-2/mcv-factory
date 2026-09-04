from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


class RecipeError(RuntimeError):
    """Raised when a trusted scaffold or verification recipe fails."""


class ProviderView(Protocol):
    provider_id: str
    provider_version: str
    executable: str


@dataclass(frozen=True)
class ScaffoldResult:
    command_result: dict[str, Any]
    layout: dict[str, str]


def run_command(
    command: list[str],
    cwd: Path,
    *,
    timeout: int = 180,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        raise RecipeError(
            f"Command timed out after {timeout}s: " + " ".join(command) + "\n" + str(stdout) + str(stderr)
        ) from exc
    result = {
        "command": command,
        "cwd": str(cwd),
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    if completed.returncode != 0:
        raise RecipeError("Command failed: " + " ".join(command) + "\n" + completed.stdout + completed.stderr)
    return result


def portable_command_result(
    result: dict[str, Any], *, project_root: Path, staging_root: Path | None = None
) -> dict[str, Any]:
    replacements = [(str(project_root), "<PROJECT_ROOT>")]
    if staging_root is not None:
        replacements.append((str(staging_root), "<STAGING_ROOT>"))

    def clean(value: str) -> str:
        out = value
        for source, target in replacements:
            out = out.replace(source, target)
        return out

    command: list[str] = []
    for index, item in enumerate(result["command"]):
        command.append(Path(item).name if index == 0 else clean(item))
    return {
        "command": command,
        "cwd": ".",
        "returncode": result["returncode"],
        "stdout": clean(result.get("stdout") or ""),
        "stderr": clean(result.get("stderr") or ""),
    }


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


PYTEST_PIN = "8.3.5"


def _python_package_name(project_name: str) -> str:
    value = re.sub(r"[-.]+", "_", project_name).lower()
    if not value.isidentifier():
        raise RecipeError(f"Project name {project_name!r} cannot map to a safe Python package name.")
    return value


def _npm_package_name(project_name: str) -> str:
    value = project_name.casefold().replace("_", "-")
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", value):
        raise RecipeError(f"Project name {project_name!r} cannot map to a safe npm package name.")
    return value


def _patch_python_pyproject(path: Path, purpose: str) -> None:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r'description = "[^"]*"', f"description = {json.dumps(purpose, ensure_ascii=False)}", text, count=1)
    text = re.sub(r'requires-python = "[^"]*"', 'requires-python = ">=3.11"', text, count=1)
    path.write_text(text, encoding="utf-8")


def _align_cli_script_name(project_root: Path, project_name: str, package_name: str) -> None:
    """Force the generated console-script key to equal ``project_name``.

    ``uv init --app`` normalizes the script name (e.g. ``demo_cli_tool`` becomes
    ``demo-cli-tool``), but the ``python-cli`` verification gate runs
    ``uv run <project_name>``. A name mismatch makes the gate report
    ``Failed to spawn: <project_name> -- program not found`` even though the
    scaffold is correct. Pinning the key to ``project_name`` keeps the gate
    honest (it tests the real ``uv run <project_name>`` entry point) and matches
    what a user expects. Console-script keys accept underscores, hyphens, dots.
    """
    pyproject = project_root / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    target = f"{package_name}:main"
    new_text = re.sub(
        r"^[A-Za-z0-9_.\-]+ = " + re.escape(f'"{target}"'),
        f'{project_name} = "{target}"',
        text,
        count=1,
        flags=re.MULTILINE,
    )
    pyproject.write_text(new_text, encoding="utf-8")


def _render_python_cli(project_name: str, purpose: str) -> str:
    return f'''from __future__ import annotations\n\nimport argparse\n\n__version__ = "0.1.0"\nPURPOSE = {purpose!r}\n\n\ndef greet(name: str) -> str:\n    """示例功能：拼接问候语，可被测试直接断言。"""\n    return f"Hello, {{name}}!"\n\n\ndef add_numbers(left: int, right: int) -> int:\n    """示例功能：整数加法，可被测试直接断言。"""\n    return left + right\n\n\ndef build_parser() -> argparse.ArgumentParser:\n    parser = argparse.ArgumentParser(prog={project_name!r}, description=PURPOSE)\n    parser.add_argument("--version", action="version", version=f"%(prog)s {{__version__}}")\n    parser.add_argument("--name", default=None, help="Name to greet (demo).")\n    parser.add_argument("--add", nargs=2, type=int, metavar=("LEFT", "RIGHT"), help="Add two integers (demo).")\n    return parser\n\n\ndef main(argv: list[str] | None = None) -> None:\n    args = build_parser().parse_args(argv)\n    if args.add is not None:\n        print(add_numbers(args.add[0], args.add[1]))\n        return\n    if args.name is not None:\n        print(greet(args.name))\n        return\n    print("Project scaffold ready. Implement domain behavior through the coding-agent workflow.")\n'''


def _render_python_cli_test(package_name: str) -> str:
    return f'''from __future__ import annotations\n\nimport io\nimport unittest\nfrom contextlib import redirect_stdout\n\nimport {package_name}\n\n\nclass SmokeTest(unittest.TestCase):\n    def test_main_runs(self) -> None:\n        stream = io.StringIO()\n        with redirect_stdout(stream):\n            {package_name}.main([])\n        self.assertIn("Project scaffold ready", stream.getvalue())\n\n    def test_version_is_defined(self) -> None:\n        self.assertEqual({package_name}.__version__, "0.1.0")\n\n\nif __name__ == "__main__":\n    unittest.main()\n'''


def _render_python_library(package_name: str) -> str:
    return f'''from __future__ import annotations\n\n__version__ = "0.1.0"\n\n\ndef scaffold_status() -> str:\n    return "{package_name} scaffold ready"\n\n\ndef greet(name: str) -> str:\n    """示例功能：拼接问候语，可被测试直接断言。"""\n    return f"Hello, {{name}}!"\n\n\ndef add_numbers(left: int, right: int) -> int:\n    """示例功能：整数加法，可被测试直接断言。"""\n    return left + right\n'''


def _render_python_cli_demo_test(package_name: str) -> str:
    return f'''from __future__ import annotations\n\nimport io\nimport unittest\nfrom contextlib import redirect_stdout\n\nfrom {package_name} import add_numbers, greet, main\n\n\nclass DemoTest(unittest.TestCase):\n    def test_greet_function(self) -> None:\n        self.assertEqual(greet("world"), "Hello, world!")\n\n    def test_add_numbers_function(self) -> None:\n        self.assertEqual(add_numbers(2, 3), 5)\n\n    def test_main_greets_with_name(self) -> None:\n        stream = io.StringIO()\n        with redirect_stdout(stream):\n            main(["--name", "world"])\n        self.assertIn("Hello, world!", stream.getvalue())\n\n    def test_main_adds_numbers(self) -> None:\n        stream = io.StringIO()\n        with redirect_stdout(stream):\n            main(["--add", "2", "3"])\n        self.assertIn("5", stream.getvalue())\n\n\nif __name__ == "__main__":\n    unittest.main()\n'''


def _render_python_library_demo_test(package_name: str) -> str:
    return f'''from __future__ import annotations\n\nimport unittest\n\nfrom {package_name} import add_numbers, greet, scaffold_status\n\n\nclass DemoTest(unittest.TestCase):\n    def test_greet_function(self) -> None:\n        self.assertEqual(greet("world"), "Hello, world!")\n\n    def test_add_numbers_function(self) -> None:\n        self.assertEqual(add_numbers(2, 3), 5)\n\n    def test_scaffold_status(self) -> None:\n        self.assertEqual(scaffold_status(), "{package_name} scaffold ready")\n\n\nif __name__ == "__main__":\n    unittest.main()\n'''


def _render_python_pytest_smoke(package_name: str) -> str:
    return f'''from __future__ import annotations

import {package_name}


def test_package_imports_under_pytest() -> None:
    assert {package_name}.__version__ == "0.1.0"
'''


def add_pinned_pytest(provider: ProviderView, project_root: Path, package_name: str) -> None:
    run_command(
        [provider.executable, "add", "--dev", f"pytest=={PYTEST_PIN}"],
        project_root,
        timeout=600,
    )
    pyproject = project_root / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    if "[tool.pytest.ini_options]" not in text:
        pyproject.write_text(
            text.rstrip() + '\n\n[tool.pytest.ini_options]\ntestpaths = ["tests"]\n',
            encoding="utf-8",
        )
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "test_pytest_smoke.py").write_text(
        _render_python_pytest_smoke(package_name), encoding="utf-8"
    )


def _render_python_library_test(package_name: str) -> str:
    return f'''from __future__ import annotations\n\nimport unittest\n\nimport {package_name}\n\n\nclass LibrarySmokeTest(unittest.TestCase):\n    def test_import_and_status(self) -> None:\n        self.assertEqual({package_name}.scaffold_status(), "{package_name} scaffold ready")\n\n    def test_version(self) -> None:\n        self.assertEqual({package_name}.__version__, "0.1.0")\n\n\nif __name__ == "__main__":\n    unittest.main()\n'''


def _scaffold_uv(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    package_name = _python_package_name(project_name)
    mode = "--app" if recipe == "uv-app" else "--lib"
    scaffold = run_command(
        [
            provider.executable,
            "init",
            mode,
            "--package",
            "--name",
            project_name,
            "--vcs",
            "none",
            "--no-pin-python",
            "--no-workspace",
            str(project_root),
        ],
        staging_root,
    )
    _patch_python_pyproject(project_root / "pyproject.toml", purpose)
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    if recipe == "uv-app":
        (project_root / "src" / package_name / "__init__.py").write_text(
            _render_python_cli(project_name, purpose), encoding="utf-8"
        )
        (tests / "test_smoke.py").write_text(_render_python_cli_test(package_name), encoding="utf-8")
        (tests / "test_demo.py").write_text(_render_python_cli_demo_test(package_name), encoding="utf-8")
        _align_cli_script_name(project_root, project_name, package_name)
    elif recipe == "uv-lib":
        (project_root / "src" / package_name / "__init__.py").write_text(
            _render_python_library(package_name), encoding="utf-8"
        )
        (tests / "test_smoke.py").write_text(_render_python_library_test(package_name), encoding="utf-8")
        (tests / "test_demo.py").write_text(_render_python_library_demo_test(package_name), encoding="utf-8")
    else:
        raise RecipeError(f"Unknown uv scaffold recipe: {recipe}")
    add_pinned_pytest(provider, project_root, package_name)
    return ScaffoldResult(
        command_result=scaffold,
        layout={"source": f"src/{package_name}/", "tests": "tests/", "packaging": "pyproject.toml"},
    )


def _npm_base_package(project_name: str, purpose: str) -> dict[str, Any]:
    return {
        "name": _npm_package_name(project_name),
        "version": "0.1.0",
        "description": purpose,
        "private": True,
        "type": "module",
    }


def _scaffold_npm(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    project_root.mkdir(parents=True, exist_ok=False)
    scaffold = run_command([provider.executable, "init", "--yes"], project_root)
    package = _npm_base_package(project_name, purpose)
    source = project_root / "src"
    tests = project_root / "tests"
    source.mkdir(parents=True, exist_ok=True)
    tests.mkdir(parents=True, exist_ok=True)

    if recipe == "npm-library":
        package.update(
            {
                "main": "./src/index.js",
                "exports": "./src/index.js",
                "scripts": {"test": "node --test"},
                "files": ["src", "README.md", "AGENTS.md", ".project", "project.lock.json"],
            }
        )
        (source / "index.js").write_text(
            'export const VERSION = "0.1.0";\n\nexport function scaffoldStatus() {\n  return "node library scaffold ready";\n}\n\nexport function capitalize(input) {\n  if (input.length === 0) return input;\n  return input.charAt(0).toUpperCase() + input.slice(1).toLowerCase();\n}\n\nexport function slugify(input) {\n  return input.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");\n}\n',
            encoding="utf-8",
        )
        (tests / "smoke.test.js").write_text(
            'import test from "node:test";\nimport assert from "node:assert/strict";\nimport { VERSION, scaffoldStatus } from "../src/index.js";\n\ntest("library imports", () => {\n  assert.equal(VERSION, "0.1.0");\n  assert.equal(scaffoldStatus(), "node library scaffold ready");\n});\n',
            encoding="utf-8",
        )
        (tests / "features.test.js").write_text(
            'import test from "node:test";\nimport assert from "node:assert/strict";\nimport { capitalize, slugify } from "../src/index.js";\n\ntest("capitalize uppercases the first letter", () => {\n  assert.equal(capitalize("hello"), "Hello");\n  assert.equal(capitalize("hELLO"), "Hello");\n  assert.equal(capitalize(""), "");\n});\n\ntest("slugify turns text into a url-safe slug", () => {\n  assert.equal(slugify("Hello, World! 2026"), "hello-world-2026");\n  assert.equal(slugify("   spaces   "), "spaces");\n});\n',
            encoding="utf-8",
        )
        layout = {"source": "src/", "tests": "tests/", "packaging": "package.json"}
    elif recipe == "npm-browser-extension":
        package.update(
            {
                "scripts": {"test": "node --test", "check:manifest": "node ./scripts/check-manifest.js"},
                "files": ["manifest.json", "popup.html", "src", "scripts", "tests", "README.md", "AGENTS.md", ".project", "project.lock.json"],
            }
        )
        scripts = project_root / "scripts"
        scripts.mkdir(parents=True, exist_ok=True)
        (project_root / "manifest.json").write_text(
            json.dumps(
                {
                    "manifest_version": 3,
                    "name": project_name,
                    "version": "0.1.0",
                    "description": purpose,
                    "action": {"default_popup": "popup.html"},
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (project_root / "popup.html").write_text(
            '<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><title>Extension scaffold</title></head>\n<body><main id="app">Project scaffold ready.</main><script type="module" src="./src/popup.js"></script></body></html>\n',
            encoding="utf-8",
        )
        (source / "popup.js").write_text(
            'export function scaffoldStatus() { return "browser extension scaffold ready"; }\n\nexport function buildMessage(text) {\n  return `Extension ready — ${text}`;\n}\n\nexport function summarizeText(text, maxLength) {\n  const trimmed = text.trim();\n  if (trimmed.length <= maxLength) return trimmed;\n  return `${trimmed.slice(0, maxLength).trimEnd()}...`;\n}\n',
            encoding="utf-8",
        )
        (scripts / "check-manifest.js").write_text(
            'import fs from "node:fs";\nconst manifest = JSON.parse(fs.readFileSync(new URL("../manifest.json", import.meta.url), "utf8"));\nif (manifest.manifest_version !== 3 || !manifest.action?.default_popup) process.exit(2);\nconsole.log("manifest ok");\n',
            encoding="utf-8",
        )
        (tests / "smoke.test.js").write_text(
            'import test from "node:test";\nimport assert from "node:assert/strict";\nimport fs from "node:fs";\nimport { scaffoldStatus } from "../src/popup.js";\n\ntest("manifest and module are usable", () => {\n  const manifest = JSON.parse(fs.readFileSync(new URL("../manifest.json", import.meta.url), "utf8"));\n  assert.equal(manifest.manifest_version, 3);\n  assert.equal(manifest.action.default_popup, "popup.html");\n  assert.equal(scaffoldStatus(), "browser extension scaffold ready");\n});\n',
            encoding="utf-8",
        )
        (tests / "features.test.js").write_text(
            'import test from "node:test";\nimport assert from "node:assert/strict";\nimport { buildMessage, summarizeText } from "../src/popup.js";\n\ntest("buildMessage prefixes popup content", () => {\n  assert.equal(buildMessage("popup ready"), "Extension ready — popup ready");\n});\n\ntest("summarizeText truncates long text with an ellipsis", () => {\n  assert.equal(summarizeText("hello world", 5), "hello...");\n  assert.equal(summarizeText("short", 20), "short");\n});\n',
            encoding="utf-8",
        )
        layout = {"source": "src/", "tests": "tests/", "manifest": "manifest.json", "packaging": "package.json"}
    else:
        raise RecipeError(f"Unknown npm scaffold recipe: {recipe}")
    _write_json(project_root / "package.json", package)
    return ScaffoldResult(command_result=scaffold, layout=layout)


def _recipe_language(recipe: str) -> str:
    """Map a scaffold recipe id to the language family used for CI/.gitignore."""
    if recipe.startswith(("uv-", "maturin-")):
        return "python"
    if recipe.startswith("npm-"):
        return "node"
    if recipe.startswith("dotnet-"):
        return "dotnet"
    if recipe.startswith(("cargo-", "game-bevy")):
        return "rust"
    if recipe.startswith("go-"):
        return "go"
    if recipe.startswith("java-"):
        return "java"
    if recipe.startswith(("kotlin-", "mobile-kotlin")):
        return "kotlin"
    if recipe.startswith(("dart-", "mobile-flutter")):
        return "dart"
    if recipe.startswith(("swift-", "mobile-swift")):
        return "swift"
    if recipe.startswith("cpp-"):
        return "cpp"
    if recipe.startswith("c-"):
        return "c"
    if recipe.startswith("php-"):
        return "php"
    if recipe.startswith("r-"):
        return "r"
    if recipe.startswith("opentofu-"):
        return "opentofu"
    if recipe.startswith("game-godot"):
        return "godot"
    if recipe.startswith("userscript-"):
        return "node"
    return "generic"


def _gitignore_for(language: str) -> str:
    rules = {
        "python": "# Python\n__pycache__/\n*.py[cod]\n.venv/\nvenv/\n.env\n*.egg-info/\nbuild/\ndist/\n.pytest_cache/\n.mypy_cache/\n.ruff_cache/\ncoverage/\n",
        "node": "# Node\nnode_modules/\ndist/\ncoverage/\n*.log\n.env\n.env.*\n.eslintcache\n.next/\nout/\n",
        "dotnet": "# .NET\nbin/\nobj/\n*.user\n.vs/\nTestResults/\n",
        "rust": "# Rust\n/target\nCargo.lock\n",
        "go": "# Go\n/bin/\n*.exe\n*.test\n*.out\n",
        "java": "# Java\ntarget/\n*.class\n*.jar\n!.mvn/wrapper/*.jar\n.idea/\n*.iml\n",
        "kotlin": "# Kotlin\nbuild/\n.idea/\n*.iml\n",
        "dart": "# Dart/Flutter\n.dart_tool/\nbuild/\n.flutter-plugins\n.packages\n",
        "swift": "# Swift\n.build/\nDerivedData/\n*.xcodeproj/xcuserdata/\n",
        "cpp": "# C/C++\nbuild/\n*.o\n*.obj\n*.exe\n*.out\n",
        "c": "# C\nbuild/\n*.o\n*.obj\n*.exe\n*.out\n",
        "php": "# PHP\n/vendor/\ncomposer.lock\n",
        "r": "# R\n.Rproj.user\n.Rhistory\n.RData\n",
        "opentofu": "# OpenTofu\n.terraform/\n*.tfstate\n*.tfstate.*\n.terraform.lock.hcl\n",
        "godot": "# Godot\n.godot/\n*.tmp\n",
        "generic": "# Build output\nbuild/\ndist/\n*.log\n.env\n",
    }
    return rules.get(language, rules["generic"])


def _ci_for(language: str, project_name: str) -> str:
    name = project_name.lower().replace(" ", "-")
    workflow = {
        "python": ("3.11", "pip install . && python -m pytest"),
        "node": ("node", "npm ci && npm test"),
        "dotnet": ("dotnet", "dotnet build --nologo && dotnet test --nologo"),
        "rust": ("rust", "cargo build --locked && cargo test"),
        "go": ("go", "go build ./... && go test ./..."),
        "java": ("java", "mvn -B verify"),
        "kotlin": ("kotlin", "gradle build"),
        "dart": ("dart", "dart pub get && dart analyze && dart test"),
        "swift": ("swift", "swift build && swift test"),
        "cpp": ("cpp", "cmake -S . -B build && cmake --build build"),
        "c": ("c", "cmake -S . -B build && cmake --build build"),
        "php": ("php", "composer install && composer test"),
        "r": ("r", "Rscript -e 'devtools::test()'"),
        "opentofu": ("opentofu", "tofu init -backend=false && tofu validate"),
        "godot": ("godot", "godot --headless --import && godot --headless -s tests/test.gd"),
        "generic": ("ubuntu", "echo 'add a build step'"),
    }
    (tool, cmd) = workflow.get(language, workflow["generic"])
    return f"""name: CI

on:
  push:
    branches: [main, master]
  pull_request:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-{tool}@v4
      - name: Install dependencies
        run: {cmd.split(" && ")[0]}
      - name: Build & test
        run: {cmd.split(" && ")[-1]}
"""


def _emit_project_meta(
    project_root: Path,
    recipe: str,
    project_name: str,
    purpose: str,
) -> None:
    """Add cross-cutting engineering files every scaffold should ship.

    One common place for every recipe (80+ blueprints) so each generated project
    is a complete, professional repository — not just loose skeleton files.
    Files already produced by the recipe itself are never overwritten.
    """
    language = _recipe_language(recipe)

    gitignore = project_root / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(_gitignore_for(language), encoding="utf-8")

    license_path = project_root / "LICENSE"
    if not license_path.exists():
        license_path.write_text(
            "MIT License\n\n"
            "Copyright (c) 2026 Project Factory contributors\n\n"
            "Permission is hereby granted, free of charge, to any person obtaining a copy\n"
            "of this software and associated documentation files (the \"Software\"), to deal\n"
            "in the Software without restriction, including without limitation the rights\n"
            "to use, copy, modify, merge, publish, distribute, sublicense, and/or sell\n"
            "copies of the Software, and to permit persons to whom the Software is\n"
            "furnished to do so, subject to the following conditions:\n\n"
            "The above copyright notice and this permission notice shall be included in all\n"
            "copies or substantial portions of the Software.\n\n"
            "THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\n"
            "IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\n"
            "FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\n"
            "AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\n"
            "LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\n"
            "OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE\n"
            "SOFTWARE.\n",
            encoding="utf-8",
        )

    changelog = project_root / "CHANGELOG.md"
    if not changelog.exists():
        changelog.write_text(
            f"# Changelog\n\nAll notable changes to `{project_name}` are documented in this file.\n\n"
            f"## [0.1.0] - {_today()}\n\n### Added\n\n- Initial Factory-generated scaffold for `{recipe}`.\n"
            "- CI, tests and documentation are ready to extend.\n",
            encoding="utf-8",
        )

    contributing = project_root / "CONTRIBUTING.md"
    if not contributing.exists():
        contributing.write_text(
            f"# Contributing to {project_name}\n\n"
            "Thanks for helping out. Please keep changes small, add tests, and document\n"
            "user-visible behavior. This project was scaffolded by Project Factory;\n"
            "verification evidence lives under `.project/evidence/`.\n",
            encoding="utf-8",
        )

    ci_dir = project_root / ".github" / "workflows"
    ci = ci_dir / "ci.yml"
    if not ci.exists():
        ci_dir.mkdir(parents=True, exist_ok=True)
        ci.write_text(_ci_for(language, project_name), encoding="utf-8")


def _today() -> str:
    from datetime import date

    return date.today().isoformat()


def scaffold_project(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
    *,
    extension_runtime: Any | None = None,
) -> ScaffoldResult:
    from .generation import first_party_scaffolds

    handlers = {
        "uv-app": _scaffold_uv,
        "uv-lib": _scaffold_uv,
        "npm-library": _scaffold_npm,
        "npm-browser-extension": _scaffold_npm,
        **first_party_scaffolds(),
    }
    handler = handlers.get(recipe)
    if handler is None and extension_runtime is not None:
        handler = getattr(extension_runtime, "scaffold_recipes", {}).get(recipe)
    if handler is None:
        raise RecipeError(f"Unknown scaffold recipe: {recipe}")
    result = handler(recipe, provider, project_name, project_root, staging_root, purpose)
    # Robustness: every blueprint, whatever its recipe, ships the shared
    # engineering files (gitignore, license, changelog, contributing, CI).
    _emit_project_meta(project_root, recipe, project_name, purpose)
    return result



def clean_ephemeral(project_root: Path) -> None:
    names = (".venv", "dist", "node_modules", "coverage", ".wxt", "target", "bin", "obj", ".next", ".pytest_cache", "site", ".astro", ".wrangler")
    for relative in names:
        target = project_root / relative
        if target.exists():
            shutil.rmtree(target)
        for nested in project_root.glob("*/" + relative):
            if nested.exists():
                shutil.rmtree(nested)
    for pycache in project_root.rglob("__pycache__"):
        shutil.rmtree(pycache, ignore_errors=True)
    for pyc in project_root.rglob("*.pyc"):
        pyc.unlink(missing_ok=True)
    for tgz in project_root.glob("*.tgz"):
        tgz.unlink(missing_ok=True)
    for vsix in project_root.glob("*.vsix"):
        vsix.unlink(missing_ok=True)
