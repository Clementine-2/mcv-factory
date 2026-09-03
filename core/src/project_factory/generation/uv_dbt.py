"""dbt analytics-transform on the uv language root.

A live warehouse is not a verification gate. Local compile uses DuckDB.
"""

from __future__ import annotations

from pathlib import Path

from ..recipes import (
    ProviderView,
    RecipeError,
    ScaffoldResult,
    _patch_python_pyproject,
    _python_package_name,
    run_command,
)

DBT_CORE_PIN = "1.9.4"
DBT_DUCKDB_PIN = "1.9.3"


def _render_project(project_name: str) -> str:
    ident = project_name.replace("-", "_")
    return (
        f"name: {ident}\n"
        "version: '0.1.0'\n"
        "profile: scaffold\n"
        "model-paths: ['models']\n"
        "clean-targets: ['target', 'dbt_packages']\n"
        "models:\n"
        f"  {ident}:\n"
        "    +materialized: view\n"
    )


def _render_profiles() -> str:
    return (
        "scaffold:\n"
        "  target: dev\n"
        "  outputs:\n"
        "    dev:\n"
        "      type: duckdb\n"
        "      path: scaffold.duckdb\n"
        "      threads: 1\n"
    )


def _render_model() -> str:
    return "select 'analytics transform scaffold ready' as status\n"


def _render_init() -> str:
    return '''from __future__ import annotations

__version__ = "0.1.0"


def scaffold_status() -> str:
    return "analytics transform scaffold ready"
'''


def _render_test(package_name: str) -> str:
    return f'''from __future__ import annotations

import unittest
from pathlib import Path

from {package_name} import scaffold_status


class SmokeTest(unittest.TestCase):
    def test_drawings_exist(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.assertTrue((root / "dbt_project.yml").is_file())
        self.assertTrue((root / "models" / "scaffold.sql").is_file())
        self.assertEqual(scaffold_status(), "analytics transform scaffold ready")


if __name__ == "__main__":
    unittest.main()
'''


def scaffold_uv_dbt(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "uv-dbt":
        raise RecipeError(f"Unsupported dbt scaffold recipe: {recipe}")
    package_name = _python_package_name(project_name)
    scaffold = run_command(
        [
            provider.executable,
            "init",
            "--lib",
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
    run_command(
        [provider.executable, "add", f"dbt-core=={DBT_CORE_PIN}", f"dbt-duckdb=={DBT_DUCKDB_PIN}"],
        project_root,
        timeout=1200,
    )
    package_dir = project_root / "src" / package_name
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "__init__.py").write_text(_render_init(), encoding="utf-8")
    (project_root / "dbt_project.yml").write_text(_render_project(project_name), encoding="utf-8")
    (project_root / "profiles.yml").write_text(_render_profiles(), encoding="utf-8")
    models = project_root / "models"
    models.mkdir(parents=True, exist_ok=True)
    (models / "scaffold.sql").write_text(_render_model(), encoding="utf-8")
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "test_smoke.py").write_text(_render_test(package_name), encoding="utf-8")
    return ScaffoldResult(
        command_result=scaffold,
        layout={
            "config": "dbt_project.yml",
            "models": "models/",
            "packaging": "pyproject.toml",
        },
    )
