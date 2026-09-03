"""Reproducible Python notebook on the uv language root.

Aligns with golden 04 (notebook / experiment / research-result).
The notebook is nbformat v4. Code cells run in-process; JupyterLab is not a gate.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..recipes import (
    ProviderView,
    RecipeError,
    ScaffoldResult,
    _patch_python_pyproject,
    _python_package_name,
    run_command,
)


def _notebook_document(purpose: str) -> dict[str, object]:
    cells = [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "# Reproducible experiment\n",
                "\n",
                f"{purpose}\n",
                "\n",
                "Parameters live in `params.json`. Data origins live in `data/SOURCES.md`.\n",
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "from pathlib import Path\n",
                "import csv\n",
                "import json\n",
                "\n",
                "PARAMS = json.loads(Path('params.json').read_text(encoding='utf-8'))\n",
                "SOURCE_NOTE = Path('data/SOURCES.md').read_text(encoding='utf-8')\n",
                "sample = Path(PARAMS['sample_path']).read_text(encoding='utf-8')\n",
                "rows = list(csv.DictReader(sample.splitlines()))\n",
                "RESULT = {\n",
                "    'n_rows': len(rows),\n",
                "    'seed': PARAMS['seed'],\n",
                "    'repeat': PARAMS['repeat'],\n",
                "    'has_provenance': 'factory-scaffold' in SOURCE_NOTE,\n",
                "}\n",
                "print('notebook scaffold ready')\n",
                "print(RESULT)\n",
            ],
        },
    ]
    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "pygments_lexer": "ipython3"},
        },
        "cells": cells,
    }


def _render_execute(package_name: str) -> str:
    return f'''from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

NOTEBOOK_PATH = Path("notebooks/experiment.ipynb")
PARAMS_PATH = Path("params.json")
SOURCES_PATH = Path("data/SOURCES.md")
EVIDENCE_PATH = Path(".project/evidence/notebook-execution.json")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_notebook(path: Path) -> dict[str, Any]:
    notebook = json.loads(path.read_text(encoding="utf-8"))
    if notebook.get("nbformat") != 4:
        raise ValueError(f"Expected nbformat 4, got {{notebook.get('nbformat')!r}}")
    if not isinstance(notebook.get("cells"), list):
        raise ValueError("Notebook is missing cells")
    return notebook


def execute_notebook(project_root: Path | None = None) -> dict[str, Any]:
    root = Path(project_root) if project_root is not None else Path.cwd()
    notebook = _load_notebook(root / NOTEBOOK_PATH)
    params_text = (root / PARAMS_PATH).read_text(encoding="utf-8")
    sources_text = (root / SOURCES_PATH).read_text(encoding="utf-8")
    params = json.loads(params_text)
    namespace: dict[str, Any] = {{"__name__": "__main__"}}
    for cell in notebook["cells"]:
        if cell.get("cell_type") != "code":
            continue
        source = cell.get("source") or []
        text = source if isinstance(source, str) else "".join(source)
        exec(compile(text, str(NOTEBOOK_PATH), "exec"), namespace)
    result = namespace.get("RESULT")
    if not isinstance(result, dict):
        raise RuntimeError("Notebook did not assign a RESULT mapping")
    evidence = {{
        "status": "executed",
        "notebook": NOTEBOOK_PATH.as_posix(),
        "params_sha256": _sha256_text(params_text),
        "sources_sha256": _sha256_text(sources_text),
        "params": params,
        "result": result,
    }}
    evidence_path = root / EVIDENCE_PATH
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\\n", encoding="utf-8")
    print("notebook scaffold ready")
    return evidence


def main() -> None:
    execute_notebook()


if __name__ == "__main__":
    main()
'''


def _render_init() -> str:
    return '''from __future__ import annotations

from .execute import execute_notebook, main

__all__ = ["execute_notebook", "main"]
'''


def _render_unittest(package_name: str) -> str:
    return f'''from __future__ import annotations

import json
import unittest
from pathlib import Path

from {package_name}.execute import PARAMS_PATH, SOURCES_PATH, execute_notebook, _load_notebook


class NotebookSmokeTest(unittest.TestCase):
    def test_notebook_executes_and_keeps_provenance(self) -> None:
        root = Path.cwd()
        notebook = _load_notebook(root / "notebooks/experiment.ipynb")
        self.assertEqual(notebook["nbformat"], 4)
        evidence = execute_notebook(root)
        self.assertEqual(evidence["status"], "executed")
        self.assertGreater(evidence["result"]["n_rows"], 0)
        self.assertTrue(evidence["result"]["has_provenance"])
        params = json.loads((root / PARAMS_PATH).read_text(encoding="utf-8"))
        self.assertEqual(evidence["params"], params)
        sources = (root / SOURCES_PATH).read_text(encoding="utf-8")
        self.assertIn("factory-scaffold", sources)
        self.assertTrue((root / ".project/evidence/notebook-execution.json").is_file())


if __name__ == "__main__":
    unittest.main()
'''


def _render_sources() -> str:
    return """# Data provenance

| path | origin | note |
| --- | --- | --- |
| `data/sample.csv` | factory-scaffold | Tiny deterministic fixture. Not an external dataset. |

Replace this table when you add real inputs. Keep the origin and a hash or URL for every file the notebook reads.
"""


def scaffold_uv_notebook(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "uv-notebook":
        raise RecipeError(f"Unsupported notebook scaffold recipe: {recipe}")
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
    (package_dir / "execute.py").write_text(_render_execute(package_name), encoding="utf-8")
    (package_dir / "__init__.py").write_text(_render_init(), encoding="utf-8")

    notebooks = project_root / "notebooks"
    notebooks.mkdir(parents=True, exist_ok=True)
    (notebooks / "experiment.ipynb").write_text(
        json.dumps(_notebook_document(purpose), ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    (project_root / "params.json").write_text(
        json.dumps({"seed": 0, "repeat": 3, "sample_path": "data/sample.csv"}, indent=2) + "\n",
        encoding="utf-8",
    )
    data = project_root / "data"
    data.mkdir(parents=True, exist_ok=True)
    (data / "SOURCES.md").write_text(_render_sources(), encoding="utf-8")
    (data / "sample.csv").write_text("x,y\n1,2\n3,6\n", encoding="utf-8")

    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "test_smoke.py").write_text(_render_unittest(package_name), encoding="utf-8")
    return ScaffoldResult(
        command_result=scaffold,
        layout={
            "source": f"src/{package_name}/",
            "notebook": "notebooks/experiment.ipynb",
            "params": "params.json",
            "data": "data/",
            "tests": "tests/",
            "packaging": "pyproject.toml",
        },
    )
