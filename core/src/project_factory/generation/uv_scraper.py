"""Local HTML scraper on the uv language root.

Not Scrapy. Fetching the live web is not a verification gate.
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

BS4_PIN = "4.12.3"


def _render_scraper() -> str:
    return '''from __future__ import annotations

import re

from bs4 import BeautifulSoup

_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def scaffold_status() -> str:
    return "scraper scaffold ready"


def extract_status(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    node = soup.select_one("#status")
    if node is None or node.string is None:
        raise ValueError("missing #status")
    return node.string.strip()


def extract_title(html: str) -> str | None:
    """真实示例：用正则从 HTML 文本中提取 <title> 内容，不联网。"""
    match = _TITLE_RE.search(html)
    if match is None:
        return None
    return match.group(1).strip()
'''


def _render_init(package_name: str) -> str:
    return f'''from __future__ import annotations

from {package_name}.scraper import extract_status, extract_title, scaffold_status

__version__ = "0.1.0"
__all__ = ["extract_status", "extract_title", "scaffold_status", "__version__"]
'''


def _render_fixture() -> str:
    return (
        "<!doctype html><html><body>"
        '<main id="status">scraper scaffold ready</main>'
        "</body></html>\n"
    )


def _render_test(package_name: str) -> str:
    return f'''from __future__ import annotations

import unittest
from pathlib import Path

from {package_name}.scraper import extract_status, scaffold_status


class SmokeTest(unittest.TestCase):
    def test_extracts_status_from_local_fixture(self) -> None:
        html = (Path(__file__).resolve().parents[1] / "fixtures" / "page.html").read_text(encoding="utf-8")
        self.assertEqual(extract_status(html), "scraper scaffold ready")
        self.assertEqual(scaffold_status(), "scraper scaffold ready")


if __name__ == "__main__":
    unittest.main()
'''


def _render_demo_test(package_name: str) -> str:
    return f'''from __future__ import annotations

import unittest

from {package_name}.scraper import extract_title


class DemoTest(unittest.TestCase):
    def test_extracts_title(self) -> None:
        html = "<html><head><title> Hello World </title></head></html>"
        self.assertEqual(extract_title(html), "Hello World")

    def test_title_is_case_insensitive_and_multiline(self) -> None:
        html = "<HTML><HEAD>\\n  <TITLE>multi\\nline</TITLE>\\n</HEAD></HTML>"
        self.assertEqual(extract_title(html), "multi\\nline")

    def test_missing_title_returns_none(self) -> None:
        self.assertIsNone(extract_title("<html><body>no title</body></html>"))


if __name__ == "__main__":
    unittest.main()
'''


def scaffold_uv_scraper(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "uv-scraper":
        raise RecipeError(f"Unsupported scraper scaffold recipe: {recipe}")
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
    run_command([provider.executable, "add", f"beautifulsoup4=={BS4_PIN}"], project_root, timeout=600)
    package_dir = project_root / "src" / package_name
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "scraper.py").write_text(_render_scraper(), encoding="utf-8")
    (package_dir / "__init__.py").write_text(_render_init(package_name), encoding="utf-8")
    fixtures = project_root / "fixtures"
    fixtures.mkdir(parents=True, exist_ok=True)
    (fixtures / "page.html").write_text(_render_fixture(), encoding="utf-8")
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "test_smoke.py").write_text(_render_test(package_name), encoding="utf-8")
    (tests / "test_demo.py").write_text(_render_demo_test(package_name), encoding="utf-8")
    add_pinned_pytest(provider, project_root, package_name)
    return ScaffoldResult(
        command_result=scaffold,
        layout={
            "source": f"src/{package_name}/",
            "fixtures": "fixtures/",
            "tests": "tests/",
            "packaging": "pyproject.toml",
        },
    )
