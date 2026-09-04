"""Minimal Python data pipeline on the uv language root.

Not Dagster/Airflow. A scheduler is not a verification gate.
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


def _render_pipeline() -> str:
    return '''from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any


def scaffold_status() -> str:
    return "data pipeline scaffold ready"


def transform(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        item = dict(row)
        item["status"] = scaffold_status()
        out.append(item)
    return out


def transform_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """真实示例：把行里的数值字段类型化，并计算 total = price * quantity。"""
    out = []
    for row in rows:
        item = dict(row)
        item["price"] = float(item["price"])
        item["quantity"] = int(item["quantity"])
        item["total"] = item["price"] * item["quantity"]
        out.append(item)
    return out


def transform_csv(csv_text: str) -> list[dict[str, Any]]:
    """真实示例：把 CSV 文本解析成行并做类型化转换。"""
    reader = csv.DictReader(io.StringIO(csv_text))
    return transform_rows([{key: value for key, value in row.items()} for row in reader])


def run(input_path: Path, output_path: Path) -> Path:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(transform(payload), ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
    return output_path
'''


def _render_init(package_name: str) -> str:
    return f'''from __future__ import annotations

from {package_name}.pipeline import run, scaffold_status, transform, transform_csv, transform_rows

__version__ = "0.1.0"
__all__ = ["run", "scaffold_status", "transform", "transform_csv", "transform_rows", "__version__"]
'''


def _render_test(package_name: str) -> str:
    return f'''from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from {package_name}.pipeline import run, scaffold_status, transform


class SmokeTest(unittest.TestCase):
    def test_transform_stamps_status(self) -> None:
        rows = transform([{{"id": 1}}])
        self.assertEqual(rows[0]["status"], "data pipeline scaffold ready")
        self.assertEqual(scaffold_status(), "data pipeline scaffold ready")

    def test_run_writes_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "input.json"
            dest = Path(tmp) / "output.json"
            src.write_text('[{{"id": 1}}]', encoding="utf-8")
            run(src, dest)
            payload = json.loads(dest.read_text(encoding="utf-8"))
            self.assertEqual(payload[0]["id"], 1)
            self.assertEqual(payload[0]["status"], "data pipeline scaffold ready")


if __name__ == "__main__":
    unittest.main()
'''


def _render_demo_test(package_name: str) -> str:
    return f'''from __future__ import annotations

import unittest

from {package_name}.pipeline import transform_csv, transform_rows


class DemoTest(unittest.TestCase):
    def test_transform_rows_types_and_totals(self) -> None:
        rows = transform_rows([
            {{"price": "2.5", "quantity": "4"}},
            {{"price": "1.0", "quantity": "10"}},
        ])
        self.assertEqual(rows[0]["price"], 2.5)
        self.assertEqual(rows[0]["quantity"], 4)
        self.assertEqual(rows[0]["total"], 10.0)
        self.assertEqual(rows[1]["total"], 10.0)

    def test_transform_csv_parses_header(self) -> None:
        rows = transform_csv("price,quantity\\n2.5,4\\n1.0,10\\n")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["total"], 10.0)
        self.assertEqual(rows[1]["total"], 10.0)


if __name__ == "__main__":
    unittest.main()
'''


def scaffold_uv_data_pipeline(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "uv-data-pipeline":
        raise RecipeError(f"Unsupported data pipeline scaffold recipe: {recipe}")
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
    (package_dir / "pipeline.py").write_text(_render_pipeline(), encoding="utf-8")
    (package_dir / "__init__.py").write_text(_render_init(package_name), encoding="utf-8")
    data = project_root / "data"
    data.mkdir(parents=True, exist_ok=True)
    (data / "input.json").write_text('[{"id": 1, "source": "fixture"}]\n', encoding="utf-8")
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "test_smoke.py").write_text(_render_test(package_name), encoding="utf-8")
    (tests / "test_demo.py").write_text(_render_demo_test(package_name), encoding="utf-8")
    add_pinned_pytest(provider, project_root, package_name)
    return ScaffoldResult(
        command_result=scaffold,
        layout={
            "source": f"src/{package_name}/",
            "pipeline": f"src/{package_name}/pipeline.py",
            "data": "data/",
            "tests": "tests/",
            "packaging": "pyproject.toml",
        },
    )
