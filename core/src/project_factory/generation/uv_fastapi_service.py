"""Minimal FastAPI HTTP service on the uv language root.

Aligns with golden 03's service work product. Not the official fullstack template.
"""

from __future__ import annotations

from pathlib import Path

from ..recipes import (
    ProviderView,
    RecipeError,
    ScaffoldResult,
    _patch_python_pyproject,
    _python_package_name,
    run_command,
)


def _render_main(package_name: str, purpose: str) -> str:
    return f'''from __future__ import annotations

from fastapi import FastAPI

from {package_name}.routers import health, items

PURPOSE = {purpose!r}

app = FastAPI(title={package_name!r}, description=PURPOSE)
app.include_router(health.router)
app.include_router(items.router)


def main() -> None:
    import uvicorn

    uvicorn.run("{package_name}.main:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
'''


def _render_health() -> str:
    return '''from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
'''


def _render_items() -> str:
    return '''from __future__ import annotations

from fastapi import APIRouter, Query

router = APIRouter()

# 示例数据：内存中的商品列表，用于演示 GET /items 的限额能力。
ITEMS = [
    {"id": 1, "name": "alpha"},
    {"id": 2, "name": "beta"},
    {"id": 3, "name": "gamma"},
]


@router.get("/items")
def list_items(limit: int = Query(10, ge=0)) -> dict[str, object]:
    """真实可运行的示例 endpoint：返回最多 limit 条商品。"""
    return {"items": ITEMS[:limit], "total": len(ITEMS)}
'''


def _render_routers_init() -> str:
    return "from . import health, items\n"


def _render_pkg_init() -> str:
    return "from .main import app, main\n\n__all__ = ['app', 'main']\n"


def _render_unittest(package_name: str) -> str:
    return f'''from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from {package_name}.main import app


class HealthSmokeTest(unittest.TestCase):
    def test_health(self) -> None:
        client = TestClient(app)
        response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {{"status": "ok"}})


if __name__ == "__main__":
    unittest.main()
'''


def _render_demo_test(package_name: str) -> str:
    return f'''from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from {package_name}.main import app


class ItemsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_items_returns_all_by_default(self) -> None:
        response = self.client.get("/items")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 3)
        self.assertEqual(len(data["items"]), 3)

    def test_items_respects_limit(self) -> None:
        response = self.client.get("/items?limit=2")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["items"]), 2)
        self.assertEqual(data["items"][0]["name"], "alpha")

    def test_items_limit_zero_returns_empty(self) -> None:
        response = self.client.get("/items?limit=0")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"], [])


if __name__ == "__main__":
    unittest.main()
'''


def _render_uvicorn_config(project_name: str) -> str:
    return f'''# Uvicorn drawing for {project_name} (F03). Not a live port claim.
# Usage: uvicorn {project_name.replace("-", "_")}.main:app --host 127.0.0.1 --port 8000
# Keep TestClient green; live binding stays UNVERIFIED.
host = "127.0.0.1"
port = 8000
reload = False
workers = 1
'''


def scaffold_uv_fastapi_service(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "uv-fastapi-service":
        raise RecipeError(f"Unsupported FastAPI scaffold recipe: {recipe}")
    package_name = _python_package_name(project_name)
    scaffold = run_command(
        [
            provider.executable,
            "init",
            "--app",
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
    run_command([provider.executable, "add", "fastapi", "uvicorn", "httpx"], project_root, timeout=600)
    package_dir = project_root / "src" / package_name
    routers = package_dir / "routers"
    routers.mkdir(parents=True, exist_ok=True)
    (package_dir / "main.py").write_text(_render_main(package_name, purpose), encoding="utf-8")
    (package_dir / "__init__.py").write_text(_render_pkg_init(), encoding="utf-8")
    (routers / "__init__.py").write_text(_render_routers_init(), encoding="utf-8")
    (routers / "health.py").write_text(_render_health(), encoding="utf-8")
    (routers / "items.py").write_text(_render_items(), encoding="utf-8")
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "test_smoke.py").write_text(_render_unittest(package_name), encoding="utf-8")
    (tests / "test_demo.py").write_text(_render_demo_test(package_name), encoding="utf-8")
    # F03: optional uvicorn config drawing, not a live port claim
    (project_root / "uvicorn.py").write_text(_render_uvicorn_config(project_name), encoding="utf-8")
    return ScaffoldResult(
        command_result=scaffold,
        layout={
            "source": f"src/{package_name}/",
            "app": f"src/{package_name}/main.py",
            "routers": f"src/{package_name}/routers/",
            "tests": "tests/",
            "packaging": "pyproject.toml",
            "uvicorn": "uvicorn.py",
        },
    )
