"""Local agent-workflow graph on the uv language root.

This is a generated user-project workflow, not the factory brain.
Live LLM calls are not a verification gate.
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


def _render_workflow() -> str:
    return '''from __future__ import annotations

from typing import Any


def scaffold_status() -> str:
    return "agent workflow scaffold ready"


def run_workflow(payload: dict[str, Any]) -> dict[str, Any]:
    return {"status": scaffold_status(), "echo": dict(payload)}
'''


def _render_init(package_name: str) -> str:
    return f'''from __future__ import annotations

from {package_name}.workflow import run_workflow, scaffold_status

__version__ = "0.1.0"
__all__ = ["run_workflow", "scaffold_status", "__version__"]
'''


def _render_test(package_name: str) -> str:
    return f'''from __future__ import annotations

import unittest

from {package_name}.workflow import run_workflow, scaffold_status


class SmokeTest(unittest.TestCase):
    def test_workflow_echoes_payload(self) -> None:
        result = run_workflow({{"step": "ping"}})
        self.assertEqual(result["status"], "agent workflow scaffold ready")
        self.assertEqual(result["echo"]["step"], "ping")
        self.assertEqual(scaffold_status(), "agent workflow scaffold ready")


if __name__ == "__main__":
    unittest.main()
'''


def scaffold_uv_agent_workflow(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "uv-agent-workflow":
        raise RecipeError(f"Unsupported agent-workflow scaffold recipe: {recipe}")
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
    (package_dir / "workflow.py").write_text(_render_workflow(), encoding="utf-8")
    (package_dir / "__init__.py").write_text(_render_init(package_name), encoding="utf-8")
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "test_smoke.py").write_text(_render_test(package_name), encoding="utf-8")
    add_pinned_pytest(provider, project_root, package_name)
    return ScaffoldResult(
        command_result=scaffold,
        layout={
            "source": f"src/{package_name}/",
            "workflow": f"src/{package_name}/workflow.py",
            "tests": "tests/",
            "packaging": "pyproject.toml",
        },
    )
