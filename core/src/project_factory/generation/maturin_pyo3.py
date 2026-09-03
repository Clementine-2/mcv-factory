"""Python native extension via pinned maturin + PyO3.

uv remains the Python language root. maturin 1.8.3 must be on PATH; other
versions fail closed. Observed newer maturin is not auto-promoted.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from ..recipes import (
    ProviderView,
    RecipeError,
    ScaffoldResult,
    _python_package_name,
    run_command,
)

MATURIN_PIN = "1.8.3"
_CRATE = re.compile(r"^[a-z][a-z0-9_]*$")


def _module_name(project_name: str) -> str:
    value = _python_package_name(project_name)
    if not _CRATE.fullmatch(value):
        raise RecipeError(f"Project name {project_name!r} cannot map to a PyO3 module name.")
    return value


def _find_maturin() -> str:
    found = shutil.which("maturin")
    if not found:
        bundled = Path(__file__).resolve().parents[3] / ".tools" / "maturin_py" / "bin" / "maturin.exe"
        if bundled.is_file():
            found = str(bundled)
    if not found:
        raise RecipeError("maturin 1.8.3 is required on PATH to generate a native extension.")
    return found


def _assert_pinned(maturin: str, cwd: Path) -> None:
    result = run_command([maturin, "--version"], cwd)
    output = str(result.get("stdout", "")) + str(result.get("stderr", ""))
    if MATURIN_PIN not in output:
        raise RecipeError(
            f"maturin {MATURIN_PIN} is supported; runtime reported {output.strip()!r}."
        )


def _render_lib(module: str) -> str:
    return f'''use pyo3::prelude::*;

#[pyfunction]
fn scaffold_status() -> String {{
    "{module} scaffold ready".to_string()
}}

#[pymodule]
fn {module}(m: &Bound<'_, PyModule>) -> PyResult<()> {{
    m.add_function(wrap_pyfunction!(scaffold_status, m)?)?;
    Ok(())
}}
'''


def _render_test(module: str) -> str:
    return f'''from __future__ import annotations

import unittest

import {module}


class SmokeTest(unittest.TestCase):
    def test_status(self) -> None:
        self.assertEqual({module}.scaffold_status(), "{module} scaffold ready")


if __name__ == "__main__":
    unittest.main()
'''


def scaffold_maturin_pyo3(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "maturin-pyo3":
        raise RecipeError(f"Unsupported maturin scaffold recipe: {recipe}")
    module = _module_name(project_name)
    maturin = _find_maturin()
    _assert_pinned(maturin, staging_root)
    scaffold = run_command(
        [maturin, "new", "-b", "pyo3", "--name", module, str(project_root)],
        staging_root,
    )
    lib_rs = _render_lib(module)
    (project_root / "src" / "lib.rs").write_text(
        lib_rs
        + "\n#[cfg(test)]\nmod tests {\n    #[test]\n    fn status_text() {\n        assert!(super::scaffold_status().contains(\"scaffold ready\"));\n    }\n}\n",
        encoding="utf-8",
    )
    return ScaffoldResult(
        command_result=scaffold,
        layout={"source": "src/lib.rs", "packaging": "pyproject.toml"},
    )
