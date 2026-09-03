"""Starlette WebSocket realtime service on the uv language root.

Binding a port is not a verification gate.
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

STARLETTE_PIN = "0.45.3"
HTTPX_PIN = "0.28.1"


def _render_app() -> str:
    return '''from __future__ import annotations

from starlette.applications import Starlette
from starlette.routing import WebSocketRoute
from starlette.websockets import WebSocket


def scaffold_status() -> str:
    return "realtime scaffold ready"


async def status_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_text(scaffold_status())
    await websocket.close()


app = Starlette(routes=[WebSocketRoute("/ws", status_socket)])
'''


def _render_init(package_name: str) -> str:
    return f'''from __future__ import annotations

from {package_name}.app import app, scaffold_status

__version__ = "0.1.0"
__all__ = ["app", "scaffold_status", "__version__"]
'''


def _render_test(package_name: str) -> str:
    return f'''from __future__ import annotations

import unittest

from starlette.testclient import TestClient

from {package_name}.app import app, scaffold_status


class SmokeTest(unittest.TestCase):
    def test_websocket_status(self) -> None:
        with TestClient(app) as client:
            with client.websocket_connect("/ws") as websocket:
                self.assertEqual(websocket.receive_text(), "realtime scaffold ready")
        self.assertEqual(scaffold_status(), "realtime scaffold ready")


if __name__ == "__main__":
    unittest.main()
'''


def scaffold_uv_realtime(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "uv-realtime":
        raise RecipeError(f"Unsupported realtime scaffold recipe: {recipe}")
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
    run_command(
        [provider.executable, "add", f"starlette=={STARLETTE_PIN}", f"httpx=={HTTPX_PIN}"],
        project_root,
        timeout=600,
    )
    package_dir = project_root / "src" / package_name
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "app.py").write_text(_render_app(), encoding="utf-8")
    (package_dir / "__init__.py").write_text(_render_init(package_name), encoding="utf-8")
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "test_smoke.py").write_text(_render_test(package_name), encoding="utf-8")
    add_pinned_pytest(provider, project_root, package_name)
    return ScaffoldResult(
        command_result=scaffold,
        layout={
            "source": f"src/{package_name}/",
            "app": f"src/{package_name}/app.py",
            "tests": "tests/",
            "packaging": "pyproject.toml",
        },
    )
