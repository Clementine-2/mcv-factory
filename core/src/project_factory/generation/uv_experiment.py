"""Reproducible experiment repo on the uv language root.

This is not a Jupyter notebook. Training a model is not a verification gate.
"""

from __future__ import annotations

import json
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


def _render_experiment() -> str:
    return '''from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence


def scaffold_status() -> str:
    return "experiment scaffold ready"


def mean(values: Sequence[float]) -> float:
    """真实可运行的实验指标示例：计算均值。"""
    if not values:
        return 0.0
    return sum(values) / len(values)


def run_experiment(params_path: Path, results_path: Path) -> dict[str, Any]:
    params = json.loads(params_path.read_text(encoding="utf-8"))
    payload = {
        "status": scaffold_status(),
        "seed": params["seed"],
        "n": params["n"],
        "sum": sum(range(int(params["n"]))),
    }
    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
    return payload
'''


def _render_init(package_name: str) -> str:
    return f'''from __future__ import annotations

from {package_name}.experiment import mean, run_experiment, scaffold_status

__version__ = "0.1.0"
__all__ = ["mean", "run_experiment", "scaffold_status", "__version__"]
'''


def _render_test(package_name: str) -> str:
    return f'''from __future__ import annotations

import json
import unittest
from pathlib import Path

from {package_name}.experiment import run_experiment, scaffold_status


class SmokeTest(unittest.TestCase):
    def test_run_writes_results(self) -> None:
        root = Path(__file__).resolve().parents[1]
        dest = root / "results" / "run.json"
        payload = run_experiment(root / "params.json", dest)
        saved = json.loads(dest.read_text(encoding="utf-8"))
        self.assertEqual(payload["status"], "experiment scaffold ready")
        self.assertEqual(saved["seed"], 1)
        self.assertEqual(scaffold_status(), "experiment scaffold ready")


if __name__ == "__main__":
    unittest.main()
'''


def _render_demo_test(package_name: str) -> str:
    return f'''from __future__ import annotations

import unittest

from {package_name}.experiment import mean


class DemoTest(unittest.TestCase):
    def test_mean(self) -> None:
        self.assertEqual(mean([1.0, 2.0, 3.0]), 2.0)

    def test_mean_empty(self) -> None:
        self.assertEqual(mean([]), 0.0)


if __name__ == "__main__":
    unittest.main()
'''


def scaffold_uv_experiment(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "uv-experiment":
        raise RecipeError(f"Unsupported experiment scaffold recipe: {recipe}")
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
    (package_dir / "experiment.py").write_text(_render_experiment(), encoding="utf-8")
    (package_dir / "__init__.py").write_text(_render_init(package_name), encoding="utf-8")
    (project_root / "params.json").write_text(json.dumps({"seed": 1, "n": 4}, indent=2) + "\n", encoding="utf-8")
    (project_root / "results").mkdir(parents=True, exist_ok=True)
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "test_smoke.py").write_text(_render_test(package_name), encoding="utf-8")
    (tests / "test_demo.py").write_text(_render_demo_test(package_name), encoding="utf-8")
    add_pinned_pytest(provider, project_root, package_name)
    return ScaffoldResult(
        command_result=scaffold,
        layout={
            "source": f"src/{package_name}/",
            "params": "params.json",
            "results": "results/",
            "tests": "tests/",
            "packaging": "pyproject.toml",
        },
    )
