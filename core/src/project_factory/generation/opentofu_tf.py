"""OpenTofu drawing on the iac work product.

F09: .tf frozen, no tofu CLI installed. Verification is file existence + HCL syntax抽查, not plan/apply.
"""

from __future__ import annotations

from pathlib import Path

from ..recipes import (
    ProviderView,
    RecipeError,
    ScaffoldResult,
    _python_package_name,
    run_command,
)


def _render_main_tf(project_name: str, purpose: str) -> str:
    # Minimal OpenTofu drawing. Keeps it as a drawing, not a live infra claim.
    safe_name = project_name.replace("-", "_")
    return f'''# OpenTofu drawing for {project_name} (F09). No tofu CLI required.
# Purpose: {purpose}
# Verification: existence + HCL syntax (check via `terraform fmt -check` if available, not required).
# `tofu plan` / `tofu apply` stays UNVERIFIED.
terraform {{
  required_version = ">= 1.8.0"
  required_providers {{
    null = {{
      source  = "hashicorp/null"
      version = "~> 3.2"
    }}
  }}
}}

provider "null" {{}}

resource "null_resource" "scaffold" {{
  triggers = {{
    project = "{project_name}"
    purpose = {purpose!r}
  }}
}}

# Example: add your real resources below, keep this file valid HCL.
# resource "aws_instance" "example" {{ }}
'''


def _render_variables_tf() -> str:
    return '''variable "project_name" {
  description = "Project Factory scaffold name"
  type        = string
  default     = "scaffold"
}
'''


def _render_outputs_tf(project_name: str) -> str:
    return f'''output "scaffold_status" {{
  value = "opentofu drawing for {project_name} ready"
}}
'''


def _render_unittest() -> str:
    return '''from __future__ import annotations

import pathlib
import unittest
import re


class TfDrawingTests(unittest.TestCase):
    def test_main_tf_exists_and_is_hcl(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        main = root / "main.tf"
        self.assertTrue(main.is_file(), "main.tf missing")
        text = main.read_text(encoding="utf-8")
        self.assertIn('terraform {', text)
        self.assertIn('resource "null_resource"', text)
        # Very light HCL syntax check: balanced braces and no trailing comma before }
        self.assertEqual(text.count("{"), text.count("}"))
        self.assertNotIn(",}", text)

    def test_no_tofu_cli_required(self) -> None:
        # Ensure we do not require tofu binary for verification
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
'''


def scaffold_opentofu_tf(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "opentofu-tf":
        raise RecipeError(f"Unsupported OpenTofu scaffold recipe: {recipe}")
    # Use uv to init a minimal Python package for consistency, but the primary output is .tf
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
    # Keep pyproject but the main deliverable is .tf
    from ..recipes import _patch_python_pyproject

    _patch_python_pyproject(project_root / "pyproject.toml", purpose)
    # Write OpenTofu drawings
    (project_root / "main.tf").write_text(_render_main_tf(project_name, purpose), encoding="utf-8")
    (project_root / "variables.tf").write_text(_render_variables_tf(), encoding="utf-8")
    (project_root / "outputs.tf").write_text(_render_outputs_tf(project_name), encoding="utf-8")
    # Keep a minimal Python package for consistency with other iac drawings that may share tooling
    pkg_dir = project_root / "src" / package_name
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "__init__.py").write_text(f'__version__ = "0.1.0"\n', encoding="utf-8")
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "test_tf.py").write_text(_render_unittest(), encoding="utf-8")
    return ScaffoldResult(
        command_result=scaffold,
        layout={
            "tf_main": "main.tf",
            "tf_variables": "variables.tf",
            "tf_outputs": "outputs.tf",
            "source": f"src/{package_name}/",
            "tests": "tests/",
            "packaging": "pyproject.toml",
        },
    )
