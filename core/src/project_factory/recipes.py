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
    return f'''from __future__ import annotations\n\nimport argparse\n\n__version__ = "0.1.0"\nPURPOSE = {purpose!r}\n\n\ndef build_parser() -> argparse.ArgumentParser:\n    parser = argparse.ArgumentParser(prog={project_name!r}, description=PURPOSE)\n    parser.add_argument("--version", action="version", version=f"%(prog)s {{__version__}}")\n    return parser\n\n\ndef main(argv: list[str] | None = None) -> None:\n    build_parser().parse_args(argv)\n    print("Project scaffold ready. Implement domain behavior through the coding-agent workflow.")\n'''


def _render_python_cli_test(package_name: str) -> str:
    return f'''from __future__ import annotations\n\nimport io\nimport unittest\nfrom contextlib import redirect_stdout\n\nimport {package_name}\n\n\nclass SmokeTest(unittest.TestCase):\n    def test_main_runs(self) -> None:\n        stream = io.StringIO()\n        with redirect_stdout(stream):\n            {package_name}.main([])\n        self.assertIn("Project scaffold ready", stream.getvalue())\n\n    def test_version_is_defined(self) -> None:\n        self.assertEqual({package_name}.__version__, "0.1.0")\n\n\nif __name__ == "__main__":\n    unittest.main()\n'''


def _render_python_library(package_name: str) -> str:
    return f'''from __future__ import annotations\n\n__version__ = "0.1.0"\n\n\ndef scaffold_status() -> str:\n    return "{package_name} scaffold ready"\n'''


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
        _align_cli_script_name(project_root, project_name, package_name)
    elif recipe == "uv-lib":
        (project_root / "src" / package_name / "__init__.py").write_text(
            _render_python_library(package_name), encoding="utf-8"
        )
        (tests / "test_smoke.py").write_text(_render_python_library_test(package_name), encoding="utf-8")
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
            'export const VERSION = "0.1.0";\n\nexport function scaffoldStatus() {\n  return "node library scaffold ready";\n}\n',
            encoding="utf-8",
        )
        (tests / "smoke.test.js").write_text(
            'import test from "node:test";\nimport assert from "node:assert/strict";\nimport { VERSION, scaffoldStatus } from "../src/index.js";\n\ntest("library imports", () => {\n  assert.equal(VERSION, "0.1.0");\n  assert.equal(scaffoldStatus(), "node library scaffold ready");\n});\n',
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
            'export function scaffoldStatus() { return "browser extension scaffold ready"; }\n', encoding="utf-8"
        )
        (scripts / "check-manifest.js").write_text(
            'import fs from "node:fs";\nconst manifest = JSON.parse(fs.readFileSync(new URL("../manifest.json", import.meta.url), "utf8"));\nif (manifest.manifest_version !== 3 || !manifest.action?.default_popup) process.exit(2);\nconsole.log("manifest ok");\n',
            encoding="utf-8",
        )
        (tests / "smoke.test.js").write_text(
            'import test from "node:test";\nimport assert from "node:assert/strict";\nimport fs from "node:fs";\nimport { scaffoldStatus } from "../src/popup.js";\n\ntest("manifest and module are usable", () => {\n  const manifest = JSON.parse(fs.readFileSync(new URL("../manifest.json", import.meta.url), "utf8"));\n  assert.equal(manifest.manifest_version, 3);\n  assert.equal(manifest.action.default_popup, "popup.html");\n  assert.equal(scaffoldStatus(), "browser extension scaffold ready");\n});\n',
            encoding="utf-8",
        )
        layout = {"source": "src/", "tests": "tests/", "manifest": "manifest.json", "packaging": "package.json"}
    else:
        raise RecipeError(f"Unknown npm scaffold recipe: {recipe}")
    _write_json(project_root / "package.json", package)
    return ScaffoldResult(command_result=scaffold, layout=layout)


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
    return handler(recipe, provider, project_name, project_root, staging_root, purpose)



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
