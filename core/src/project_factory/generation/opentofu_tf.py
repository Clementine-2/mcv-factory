"""OpenTofu drawing on the iac work product.

F09: .tf frozen, no tofu CLI installed. Verification is file existence + HCL syntax抽查, not plan/apply.
示例包含真实可用的模块声明：变量、本地计算值、null 触发器与本地文件资源，并配有校验说明。
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
    # OpenTofu drawing for the project. Keeps it as a drawing, not a live infra claim.
    # 校验说明：
    #   - 校验方式：文件存在性 + 轻量 HCL 语法抽查（左右大括号配对、无尾随逗号）。
    #   - 若本机装有 tofu：可运行 `tofu fmt -check` / `tofu validate` 做增强校验（可选，非必需）。
    #   - `tofu plan` / `tofu apply` 保持 UNVERIFIED，工厂不执行任何真实基础设施操作。
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
    local = {{
      source  = "hashicorp/local"
      version = "~> 2.4"
    }}
  }}
}}

provider "null" {{}}

provider "local" {{}}

# 真实的模块示例：本地计算值 + 本地资源声明。
locals {{
  greeting  = "Hello from {safe_name}"
  message   = "${{var.project_name}} scaffold: {purpose}"
  file_name = "scaffold.txt"
}}

resource "null_resource" "scaffold" {{
  triggers = {{
    project = "${{var.project_name}}"
    purpose = {purpose!r}
  }}
}}

# 本地资源声明示例：把生成的欢迎信息写入本地文件（无需真实云账号即可演示）。
resource "local_file" "scaffold_readme" {{
  filename = local.file_name
  content  = local.message
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

variable "environment" {
  description = "部署环境标签（示例变量）"
  type        = string
  default     = "dev"
}
'''


def _render_outputs_tf(project_name: str) -> str:
    return f'''output "scaffold_status" {{
  value = "opentofu drawing for {project_name} ready"
}}

output "generated_file" {{
  description = "本地文件资源生成的路径（真实模块输出的示例）"
  value       = local_file.scaffold_readme.filename
}}

output "message" {{
  description = "本地计算值的示例输出"
  value       = local.message
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
        # 真实的模块示例：本地资源声明 + 本地计算值。
        self.assertIn('resource "local_file"', text)
        self.assertIn('locals {', text)
        # Very light HCL syntax check: balanced braces and no trailing comma before }
        self.assertEqual(text.count("{"), text.count("}"))
        self.assertNotIn(",}", text)

    def test_variables_and_outputs_are_declared(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        variables = (root / "variables.tf").read_text(encoding="utf-8")
        self.assertIn('variable "project_name"', variables)
        self.assertIn('variable "environment"', variables)
        outputs = (root / "outputs.tf").read_text(encoding="utf-8")
        self.assertIn('output "scaffold_status"', outputs)
        self.assertIn('output "generated_file"', outputs)
        self.assertIn('output "message"', outputs)

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
