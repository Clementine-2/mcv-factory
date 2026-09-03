"""MkDocs Material docs site on the uv language root.

mkdocs serve is not a verification gate.
"""

from __future__ import annotations

from pathlib import Path

from ..recipes import (
    ProviderView,
    RecipeError,
    ScaffoldResult,
    _patch_python_pyproject,
    run_command,
)

MKDOCS_PIN = "1.6.1"
MATERIAL_PIN = "9.6.11"


def _render_config(project_name: str) -> str:
    return (
        f"site_name: {project_name}\n"
        "theme:\n"
        "  name: material\n"
        "nav:\n"
        "  - Home: index.md\n"
    )


def _render_index(purpose: str) -> str:
    return (
        "# Docs scaffold\n\n"
        f"{purpose}\n\n"
        "docs site scaffold ready\n"
    )


def scaffold_uv_mkdocs(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "uv-mkdocs":
        raise RecipeError(f"Unsupported MkDocs scaffold recipe: {recipe}")
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
        [provider.executable, "add", f"mkdocs=={MKDOCS_PIN}", f"mkdocs-material=={MATERIAL_PIN}"],
        project_root,
        timeout=1200,
    )
    (project_root / "mkdocs.yml").write_text(_render_config(project_name), encoding="utf-8")
    docs = project_root / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "index.md").write_text(_render_index(purpose), encoding="utf-8")
    return ScaffoldResult(
        command_result=scaffold,
        layout={"docs": "docs/", "config": "mkdocs.yml", "packaging": "pyproject.toml"},
    )
