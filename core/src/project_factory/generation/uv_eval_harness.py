"""Python evaluation harness on the uv language root.

Model training and live leaderboards are not verification gates.
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


def _render_harness() -> str:
    return '''from __future__ import annotations

from typing import Sequence


def scaffold_status() -> str:
    return "eval harness scaffold ready"


def accuracy(gold: Sequence[str], pred: Sequence[str]) -> float:
    if not gold:
        return 0.0
    if len(gold) != len(pred):
        raise ValueError("gold and pred must have the same length")
    hits = sum(1 for left, right in zip(gold, pred, strict=True) if left == right)
    return hits / len(gold)


def f1(gold: Sequence[str], pred: Sequence[str]) -> float:
    """真实可运行的评估指标：二分类 F1。"""
    if len(gold) != len(pred):
        raise ValueError("gold and pred must have the same length")
    tp = fp = fn = 0
    for g, p in zip(gold, pred, strict=True):
        positive = g == "positive"
        if positive and p == "positive":
            tp += 1
        elif not positive and p == "positive":
            fp += 1
        elif positive and p != "positive":
            fn += 1
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)
'''


def _render_init(package_name: str) -> str:
    return f'''from __future__ import annotations

from {package_name}.harness import accuracy, f1, scaffold_status

__version__ = "0.1.0"
__all__ = ["accuracy", "f1", "scaffold_status", "__version__"]
'''


def _render_test(package_name: str) -> str:
    return f'''from __future__ import annotations

import json
import unittest
from pathlib import Path

from {package_name}.harness import accuracy, scaffold_status


class SmokeTest(unittest.TestCase):
    def test_accuracy_on_fixture(self) -> None:
        root = Path(__file__).resolve().parents[1]
        gold = json.loads((root / "fixtures" / "gold.json").read_text(encoding="utf-8"))
        pred = json.loads((root / "fixtures" / "pred.json").read_text(encoding="utf-8"))
        self.assertEqual(accuracy(gold, pred), 1.0)
        self.assertEqual(scaffold_status(), "eval harness scaffold ready")


if __name__ == "__main__":
    unittest.main()
'''


def _render_demo_test(package_name: str) -> str:
    return f'''from __future__ import annotations

import unittest

from {package_name}.harness import f1


class DemoTest(unittest.TestCase):
    def test_perfect_f1(self) -> None:
        self.assertEqual(f1(["positive", "negative"], ["positive", "negative"]), 1.0)

    def test_miss_all_positive_returns_zero(self) -> None:
        self.assertEqual(f1(["positive"], ["negative"]), 0.0)

    def test_length_mismatch_raises(self) -> None:
        with self.assertRaises(ValueError):
            f1(["positive"], ["positive", "negative"])


if __name__ == "__main__":
    unittest.main()
'''


def scaffold_uv_eval_harness(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "uv-eval-harness":
        raise RecipeError(f"Unsupported eval harness scaffold recipe: {recipe}")
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
    (package_dir / "harness.py").write_text(_render_harness(), encoding="utf-8")
    (package_dir / "__init__.py").write_text(_render_init(package_name), encoding="utf-8")
    fixtures = project_root / "fixtures"
    fixtures.mkdir(parents=True, exist_ok=True)
    (fixtures / "gold.json").write_text('["ok", "ok"]\n', encoding="utf-8")
    (fixtures / "pred.json").write_text('["ok", "ok"]\n', encoding="utf-8")
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
