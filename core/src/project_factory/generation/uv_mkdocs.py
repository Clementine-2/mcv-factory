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
    _python_package_name,
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


def _render_docgen() -> str:
    return '''from __future__ import annotations


def render_index(title: str, body: str) -> str:
    """真实可运行的文档示例：渲染一个 Markdown 首页。"""
    return f"# {title}\\n\\n{body}\\n"
'''


def _render_demo_test(package_name: str) -> str:
    return f'''from __future__ import annotations

import unittest

from {package_name}.docgen import render_index


class DemoTest(unittest.TestCase):
    def test_render_index_has_title(self) -> None:
        text = render_index("Docs scaffold", "hello")
        self.assertIn("# Docs scaffold", text)
        self.assertIn("hello", text)

    def test_render_index_ends_with_newline(self) -> None:
        self.assertTrue(render_index("T", "B").endswith("\\n"))


if __name__ == "__main__":
    unittest.main()
'''


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
    package_name = _python_package_name(project_name)
    package_dir = project_root / "src" / package_name
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "docgen.py").write_text(_render_docgen(), encoding="utf-8")
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "test_demo.py").write_text(_render_demo_test(package_name), encoding="utf-8")
    return ScaffoldResult(
        command_result=scaffold,
        layout={
            "docs": "docs/",
            "source": f"src/{package_name}/",
            "tests": "tests/",
            "config": "mkdocs.yml",
            "packaging": "pyproject.toml",
        },
    )
