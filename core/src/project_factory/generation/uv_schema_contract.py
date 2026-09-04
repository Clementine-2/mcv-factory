"""OpenAPI schema-contract repo on the uv language root.

This is the contract drawing, not a generated client. Live spec drift is unverified.
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

PYYAML_PIN = "6.0.3"


def _render_spec() -> str:
    return """openapi: 3.0.3
info:
  title: Scaffold contract
  version: 0.1.0
paths:
  /health:
    get:
      operationId: getHealth
      responses:
        "200":
          description: ok
"""


def _render_contract() -> str:
    return '''from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def scaffold_status() -> str:
    return "schema contract scaffold ready"


def load_contract(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("OpenAPI document must be a mapping")
    return payload


def resolve_path(doc: dict[str, Any], path: str) -> dict[str, Any] | None:
    """真实可运行的契约示例：解析 OpenAPI 文档中某个路径的操作定义。"""
    paths = doc.get("paths")
    if not isinstance(paths, dict):
        return None
    return paths.get(path)
'''


def _render_init(package_name: str) -> str:
    return f'''from __future__ import annotations

from {package_name}.contract import load_contract, resolve_path, scaffold_status

__version__ = "0.1.0"
__all__ = ["load_contract", "resolve_path", "scaffold_status", "__version__"]
'''


def _render_test(package_name: str) -> str:
    return f'''from __future__ import annotations

import unittest
from pathlib import Path

from {package_name}.contract import load_contract, scaffold_status


class SmokeTest(unittest.TestCase):
    def test_openapi_drawing_has_health(self) -> None:
        root = Path(__file__).resolve().parents[1]
        doc = load_contract(root / "openapi.yaml")
        self.assertEqual(doc["openapi"].startswith("3."), True)
        self.assertIn("/health", doc["paths"])
        self.assertEqual(scaffold_status(), "schema contract scaffold ready")


if __name__ == "__main__":
    unittest.main()
'''


def _render_demo_test(package_name: str) -> str:
    return f'''from __future__ import annotations

import unittest
from pathlib import Path

from {package_name}.contract import load_contract, resolve_path


class DemoTest(unittest.TestCase):
    def test_resolve_path_returns_operation(self) -> None:
        root = Path(__file__).resolve().parents[1]
        doc = load_contract(root / "openapi.yaml")
        operation = resolve_path(doc, "/health")
        self.assertIsNotNone(operation)
        self.assertIn("get", operation)

    def test_resolve_path_missing_returns_none(self) -> None:
        doc = {{"paths": {{"/health": {{"get": {{}}}}}}}}
        self.assertIsNone(resolve_path(doc, "/missing"))


if __name__ == "__main__":
    unittest.main()
'''


def scaffold_uv_schema_contract(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "uv-schema-contract":
        raise RecipeError(f"Unsupported schema-contract scaffold recipe: {recipe}")
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
    run_command([provider.executable, "add", f"PyYAML=={PYYAML_PIN}"], project_root, timeout=600)
    package_dir = project_root / "src" / package_name
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "contract.py").write_text(_render_contract(), encoding="utf-8")
    (package_dir / "__init__.py").write_text(_render_init(package_name), encoding="utf-8")
    (project_root / "openapi.yaml").write_text(_render_spec(), encoding="utf-8")
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "test_smoke.py").write_text(_render_test(package_name), encoding="utf-8")
    (tests / "test_demo.py").write_text(_render_demo_test(package_name), encoding="utf-8")
    add_pinned_pytest(provider, project_root, package_name)
    return ScaffoldResult(
        command_result=scaffold,
        layout={
            "spec": "openapi.yaml",
            "source": f"src/{package_name}/",
            "tests": "tests/",
            "packaging": "pyproject.toml",
        },
    )
