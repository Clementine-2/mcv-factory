"""In-process gRPC servicer on the uv language root.

The frozen .proto drawing is the contract. Binding a port is not a verification gate.
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


def _render_proto() -> str:
    return """syntax = "proto3";

package scaffold;

service Status {
  rpc SayStatus (StatusRequest) returns (StatusReply);
}

message StatusRequest {
  string name = 1;
}

message StatusReply {
  string status = 1;
}
"""


def _render_servicer() -> str:
    return '''from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


def scaffold_status() -> str:
    return "grpc scaffold ready"


@dataclass(frozen=True)
class StatusRequest:
    name: str


@dataclass(frozen=True)
class StatusReply:
    status: str


def compute_total(values: Sequence[int]) -> int:
    """真实可运行的 gRPC 业务示例：把一组数值求和。"""
    return sum(values)


class StatusServicer:
    def SayStatus(self, request: StatusRequest) -> StatusReply:
        return StatusReply(status=f"{scaffold_status()}:{request.name}")
'''


def _render_init(package_name: str) -> str:
    return f'''from __future__ import annotations

from {package_name}.servicer import StatusReply, StatusRequest, StatusServicer, compute_total, scaffold_status

__version__ = "0.1.0"
__all__ = ["StatusReply", "StatusRequest", "StatusServicer", "compute_total", "scaffold_status", "__version__"]
'''


def _render_test(package_name: str) -> str:
    return f'''from __future__ import annotations

import unittest
from pathlib import Path

from {package_name}.servicer import StatusRequest, StatusServicer, scaffold_status


class SmokeTest(unittest.TestCase):
    def test_proto_declares_status_service(self) -> None:
        root = Path(__file__).resolve().parents[1]
        drawing = (root / "status.proto").read_text(encoding="utf-8")
        self.assertIn("service Status", drawing)
        self.assertIn("rpc SayStatus", drawing)

    def test_in_process_say_status(self) -> None:
        reply = StatusServicer().SayStatus(StatusRequest(name="probe"))
        self.assertEqual(reply.status, "grpc scaffold ready:probe")
        self.assertEqual(scaffold_status(), "grpc scaffold ready")


if __name__ == "__main__":
    unittest.main()
'''


def _render_demo_test(package_name: str) -> str:
    return f'''from __future__ import annotations

import unittest

from {package_name}.servicer import compute_total


class DemoTest(unittest.TestCase):
    def test_compute_total(self) -> None:
        self.assertEqual(compute_total([1, 2, 3]), 6)

    def test_compute_total_empty(self) -> None:
        self.assertEqual(compute_total([]), 0)


if __name__ == "__main__":
    unittest.main()
'''


def scaffold_uv_grpc(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "uv-grpc":
        raise RecipeError(f"Unsupported gRPC scaffold recipe: {recipe}")
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
    (package_dir / "servicer.py").write_text(_render_servicer(), encoding="utf-8")
    (package_dir / "__init__.py").write_text(_render_init(package_name), encoding="utf-8")
    (project_root / "status.proto").write_text(_render_proto(), encoding="utf-8")
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "test_smoke.py").write_text(_render_test(package_name), encoding="utf-8")
    (tests / "test_demo.py").write_text(_render_demo_test(package_name), encoding="utf-8")
    add_pinned_pytest(provider, project_root, package_name)
    return ScaffoldResult(
        command_result=scaffold,
        layout={
            "proto": "status.proto",
            "source": f"src/{package_name}/",
            "tests": "tests/",
            "packaging": "pyproject.toml",
        },
    )
