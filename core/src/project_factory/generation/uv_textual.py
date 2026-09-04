"""Textual TUI on the uv language root.

Launching an interactive terminal UI is not a verification gate.
"""

from __future__ import annotations

from pathlib import Path

from ..recipes import (
    ProviderView,
    RecipeError,
    ScaffoldResult,
    add_pinned_pytest,
    _patch_python_pyproject,
    _python_package_name,
    run_command,
)

TEXTUAL_PIN = "2.1.2"


def _render_app() -> str:
    return '''from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Static


def scaffold_status() -> str:
    return "tui scaffold ready"


def build_banner(text: str, width: int = 40) -> str:
    """真实可运行的 TUI 示例：生成居中的标题横幅文本。"""
    return text.center(width)


class ScaffoldApp(App):
    def compose(self) -> ComposeResult:
        yield Static(scaffold_status(), id="status")


def main() -> None:
    ScaffoldApp().run()


if __name__ == "__main__":
    main()
'''


def _render_init(package_name: str) -> str:
    return f'''from __future__ import annotations

from {package_name}.app import ScaffoldApp, build_banner, main, scaffold_status

__version__ = "0.1.0"
__all__ = ["ScaffoldApp", "build_banner", "main", "scaffold_status", "__version__"]
'''


def _render_test(package_name: str) -> str:
    return f'''from __future__ import annotations

import unittest

from {package_name}.app import ScaffoldApp, scaffold_status


class SmokeTest(unittest.TestCase):
    def test_status_is_defined(self) -> None:
        self.assertEqual(scaffold_status(), "tui scaffold ready")

    def test_compose_yields_status_widget(self) -> None:
        widgets = list(ScaffoldApp().compose())
        self.assertEqual(len(widgets), 1)
        self.assertEqual(str(widgets[0].renderable), "tui scaffold ready")


if __name__ == "__main__":
    unittest.main()
'''


def _render_demo_test(package_name: str) -> str:
    return f'''from __future__ import annotations

import unittest

from {package_name}.app import build_banner, scaffold_status


class DemoTest(unittest.TestCase):
    def test_build_banner_centers_text(self) -> None:
        banner = build_banner("tui scaffold ready", width=30)
        self.assertEqual(banner, "tui scaffold ready".center(30))
        self.assertEqual(len(banner), 30)

    def test_build_banner_uses_default_width(self) -> None:
        self.assertEqual(len(build_banner(scaffold_status())), 40)


if __name__ == "__main__":
    unittest.main()
'''


def scaffold_uv_textual(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "uv-textual-tui":
        raise RecipeError(f"Unsupported Textual scaffold recipe: {recipe}")
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
    run_command([provider.executable, "add", f"textual=={TEXTUAL_PIN}"], project_root, timeout=600)
    package_dir = project_root / "src" / package_name
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "app.py").write_text(_render_app(), encoding="utf-8")
    (package_dir / "__init__.py").write_text(_render_init(package_name), encoding="utf-8")
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "test_smoke.py").write_text(_render_test(package_name), encoding="utf-8")
    (tests / "test_demo.py").write_text(_render_demo_test(package_name), encoding="utf-8")
    add_pinned_pytest(provider, project_root, package_name)
    return ScaffoldResult(
        command_result=scaffold,
        layout={
            "source": f"src/{package_name}/",
            "app": f"src/{package_name}/app.py",
            "tests": "tests/",
            "packaging": "pyproject.toml",
        },
    )
