"""AWS Lambda handler on the uv language root.

Deploying to AWS is not a verification gate.
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


def _render_handler() -> str:
    return '''from __future__ import annotations

from typing import Any


def scaffold_status() -> str:
    return "lambda scaffold ready"


def handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    return {"statusCode": 200, "body": scaffold_status()}


def process_event(event: dict[str, Any]) -> dict[str, Any]:
    """真实可运行的 Lambda 示例：把输入文本转大写并返回 JSON 响应。"""
    body = event.get("body") or ""
    return {"statusCode": 200, "body": body.upper()}
'''


def _render_init(package_name: str) -> str:
    return f'''from __future__ import annotations

from {package_name}.handler import handler, process_event, scaffold_status

__version__ = "0.1.0"
__all__ = ["handler", "process_event", "scaffold_status", "__version__"]
'''


def _render_test(package_name: str) -> str:
    return f'''from __future__ import annotations

import unittest

from {package_name}.handler import handler, scaffold_status


class SmokeTest(unittest.TestCase):
    def test_status_is_defined(self) -> None:
        self.assertEqual(scaffold_status(), "lambda scaffold ready")

    def test_handler_returns_ok(self) -> None:
        result = handler({{}}, None)
        self.assertEqual(result["statusCode"], 200)
        self.assertEqual(result["body"], "lambda scaffold ready")


if __name__ == "__main__":
    unittest.main()
'''


def _render_demo_test(package_name: str) -> str:
    return f'''from __future__ import annotations

import unittest

from {package_name}.handler import process_event


class DemoTest(unittest.TestCase):
    def test_process_event_uppercases_body(self) -> None:
        result = process_event({{"body": "ping"}})
        self.assertEqual(result["statusCode"], 200)
        self.assertEqual(result["body"], "PING")

    def test_process_event_missing_body(self) -> None:
        self.assertEqual(process_event({{}})["body"], "")


if __name__ == "__main__":
    unittest.main()
'''


def scaffold_uv_lambda(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "uv-lambda":
        raise RecipeError(f"Unsupported Lambda scaffold recipe: {recipe}")
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
    package_dir = project_root / "src" / package_name
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "handler.py").write_text(_render_handler(), encoding="utf-8")
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
            "handler": f"src/{package_name}/handler.py",
            "tests": "tests/",
            "packaging": "pyproject.toml",
        },
    )
