"""Typer body on the existing Python CLI line.

This is a body swap, not a new work-product kind. argparse remains the default.
"""

from __future__ import annotations

from pathlib import Path

from ..recipes import (
    ProviderView,
    RecipeError,
    ScaffoldResult,
    add_pinned_pytest,
    _align_cli_script_name,
    _patch_python_pyproject,
    _python_package_name,
    run_command,
)

TYPER_PIN = "0.15.2"


def _render_main(project_name: str, purpose: str) -> str:
    return f'''from __future__ import annotations

import typer

__version__ = "0.1.0"
PURPOSE = {purpose!r}

app = typer.Typer(add_completion=False, no_args_is_help=False)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", help="Show version and exit."),
) -> None:
    if version:
        typer.echo(f"{project_name} {{__version__}}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        typer.echo("Project scaffold ready. Implement domain behavior through the coding-agent workflow.")


def run() -> None:
    app()


if __name__ == "__main__":
    run()
'''


def _render_init() -> str:
    return '''from __future__ import annotations

from .cli import __version__, app, run as main

__all__ = ["__version__", "app", "main"]
'''


def _render_test(package_name: str) -> str:
    return f'''from __future__ import annotations

import unittest

from typer.testing import CliRunner

from {package_name}.cli import __version__, app


class SmokeTest(unittest.TestCase):
    def test_main_runs(self) -> None:
        result = CliRunner().invoke(app, [])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Project scaffold ready", result.output)

    def test_version_is_defined(self) -> None:
        result = CliRunner().invoke(app, ["--version"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("0.1.0", result.output)
        self.assertEqual(__version__, "0.1.0")


if __name__ == "__main__":
    unittest.main()
'''


def scaffold_uv_typer_cli(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "uv-typer-app":
        raise RecipeError(f"Unsupported Typer scaffold recipe: {recipe}")
    package_name = _python_package_name(project_name)
    scaffold = run_command(
        [
            provider.executable,
            "init",
            "--app",
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
    _align_cli_script_name(project_root, project_name, package_name)
    run_command([provider.executable, "add", f"typer=={TYPER_PIN}"], project_root, timeout=600)
    package_dir = project_root / "src" / package_name
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "cli.py").write_text(_render_main(project_name, purpose), encoding="utf-8")
    (package_dir / "__init__.py").write_text(_render_init(), encoding="utf-8")
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "test_smoke.py").write_text(_render_test(package_name), encoding="utf-8")
    add_pinned_pytest(provider, project_root, package_name)
    return ScaffoldResult(
        command_result=scaffold,
        layout={
            "source": f"src/{package_name}/",
            "cli": f"src/{package_name}/cli.py",
            "tests": "tests/",
            "packaging": "pyproject.toml",
        },
    )
