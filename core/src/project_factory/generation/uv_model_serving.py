"""Model-serving stub on the uv language root.

No GPU weights. Binding a port is not a verification gate.
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


def _render_serve() -> str:
    return '''from __future__ import annotations

from typing import Sequence


def scaffold_status() -> str:
    return "model serving scaffold ready"


def predict(features: Sequence[float]) -> dict[str, float | str]:
    return {"score": float(sum(features)), "status": scaffold_status()}


def normalize(features: Sequence[float]) -> list[float]:
    """真实可运行的示例：min-max 归一化到 [0, 1]。"""
    values = [float(item) for item in features]
    if not values:
        return []
    low, high = min(values), max(values)
    if low == high:
        return [0.0] * len(values)
    return [(item - low) / (high - low) for item in values]
'''


def _render_init(package_name: str) -> str:
    return f'''from __future__ import annotations

from {package_name}.serve import normalize, predict, scaffold_status

__version__ = "0.1.0"
__all__ = ["normalize", "predict", "scaffold_status", "__version__"]
'''


def _render_test(package_name: str) -> str:
    return f'''from __future__ import annotations

import unittest

from {package_name}.serve import predict, scaffold_status


class SmokeTest(unittest.TestCase):
    def test_predict_sums_features(self) -> None:
        result = predict([1.0, 2.0])
        self.assertEqual(result["score"], 3.0)
        self.assertEqual(result["status"], "model serving scaffold ready")
        self.assertEqual(scaffold_status(), "model serving scaffold ready")


if __name__ == "__main__":
    unittest.main()
'''


def _render_demo_test(package_name: str) -> str:
    return f'''from __future__ import annotations

import unittest

from {package_name}.serve import normalize


class DemoTest(unittest.TestCase):
    def test_normalize_maps_to_unit_interval(self) -> None:
        self.assertEqual(normalize([1.0, 3.0, 5.0]), [0.0, 0.5, 1.0])

    def test_normalize_constant_features(self) -> None:
        self.assertEqual(normalize([4.0, 4.0]), [0.0, 0.0])

    def test_normalize_empty(self) -> None:
        self.assertEqual(normalize([]), [])


if __name__ == "__main__":
    unittest.main()
'''


def scaffold_uv_model_serving(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "uv-model-serving":
        raise RecipeError(f"Unsupported model-serving scaffold recipe: {recipe}")
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
    (package_dir / "serve.py").write_text(_render_serve(), encoding="utf-8")
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
            "serve": f"src/{package_name}/serve.py",
            "tests": "tests/",
            "packaging": "pyproject.toml",
        },
    )
