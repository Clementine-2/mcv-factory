"""Docker Compose stack drawing on the uv language root.

A live Docker daemon is not a verification gate.
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


def _render_compose() -> str:
    return (
        "services:\n"
        "  scaffold:\n"
        "    image: alpine:3.21\n"
        "    command: ['echo', 'container stack scaffold ready']\n"
    )


def _render_stack() -> str:
    return '''from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def scaffold_status() -> str:
    return "container stack scaffold ready"


def load_compose(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("compose drawing must be a mapping")
    return payload


def service_names(doc: dict[str, Any]) -> list[str]:
    """真实可运行的示例：列出 compose 文档中的服务名。"""
    services = doc.get("services")
    if not isinstance(services, dict):
        return []
    return list(services.keys())
'''


def _render_init(package_name: str) -> str:
    return f'''from __future__ import annotations

from {package_name}.stack import load_compose, scaffold_status, service_names

__version__ = "0.1.0"
__all__ = ["load_compose", "scaffold_status", "service_names", "__version__"]
'''


def _render_test(package_name: str) -> str:
    return f'''from __future__ import annotations

import unittest
from pathlib import Path

from {package_name}.stack import load_compose, scaffold_status


class SmokeTest(unittest.TestCase):
    def test_compose_declares_scaffold_service(self) -> None:
        root = Path(__file__).resolve().parents[1]
        doc = load_compose(root / "compose.yaml")
        self.assertIn("scaffold", doc["services"])
        self.assertEqual(scaffold_status(), "container stack scaffold ready")


if __name__ == "__main__":
    unittest.main()
'''


def _render_demo_test(package_name: str) -> str:
    return f'''from __future__ import annotations

import unittest
from pathlib import Path

from {package_name}.stack import load_compose, service_names


class DemoTest(unittest.TestCase):
    def test_service_names_from_compose(self) -> None:
        root = Path(__file__).resolve().parents[1]
        doc = load_compose(root / "compose.yaml")
        self.assertEqual(service_names(doc), ["scaffold"])


if __name__ == "__main__":
    unittest.main()
'''


def scaffold_uv_compose_stack(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "uv-compose-stack":
        raise RecipeError(f"Unsupported compose-stack scaffold recipe: {recipe}")
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
    (package_dir / "stack.py").write_text(_render_stack(), encoding="utf-8")
    (package_dir / "__init__.py").write_text(_render_init(package_name), encoding="utf-8")
    (project_root / "compose.yaml").write_text(_render_compose(), encoding="utf-8")
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "test_smoke.py").write_text(_render_test(package_name), encoding="utf-8")
    (tests / "test_demo.py").write_text(_render_demo_test(package_name), encoding="utf-8")
    add_pinned_pytest(provider, project_root, package_name)
    return ScaffoldResult(
        command_result=scaffold,
        layout={"compose": "compose.yaml", "source": f"src/{package_name}/", "packaging": "pyproject.toml"},
    )
