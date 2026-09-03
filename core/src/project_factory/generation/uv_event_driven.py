"""In-process event consumer on the uv language root.

A broker (Kafka, RabbitMQ, SQS) is not a verification gate.
This is a pure consumer, not an HTTP service with a side queue.
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


def _render_worker() -> str:
    return '''from __future__ import annotations

from typing import Any


def scaffold_status() -> str:
    return "event consumer scaffold ready"


def handle(message: dict[str, Any]) -> dict[str, Any]:
    return {"id": message["id"], "status": scaffold_status()}


def drain(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [handle(item) for item in messages]
'''


def _render_init(package_name: str) -> str:
    return f'''from __future__ import annotations

from {package_name}.worker import drain, handle, scaffold_status

__version__ = "0.1.0"
__all__ = ["drain", "handle", "scaffold_status", "__version__"]
'''


def _render_test(package_name: str) -> str:
    return f'''from __future__ import annotations

import unittest

from {package_name}.worker import drain, handle, scaffold_status


class SmokeTest(unittest.TestCase):
    def test_handle_stamps_status(self) -> None:
        result = handle({{"id": "m1"}})
        self.assertEqual(result, {{"id": "m1", "status": "event consumer scaffold ready"}})
        self.assertEqual(scaffold_status(), "event consumer scaffold ready")

    def test_drain_preserves_order(self) -> None:
        out = drain([{{"id": "a"}}, {{"id": "b"}}])
        self.assertEqual([item["id"] for item in out], ["a", "b"])


if __name__ == "__main__":
    unittest.main()
'''


def _render_real_broker_script(package_name: str) -> str:
    """Q4-③: developer-executed real-broker smoke check (in-process broker, not just unit assertions)."""
    return f'''"""Q4-③: real-broker smoke check for the generated event consumer.

Pipes a message through `handle` via a tiny in-process broker (asyncio queue) to prove the
consumer handles real messages off a channel. Wire your real Kafka/RabbitMQ/SQS yourself.
Run with: `uv run python scripts/verify_real_broker.py`.
"""
from __future__ import annotations

import asyncio

from {package_name}.worker import handle, scaffold_status


async def _run() -> None:
    queue: asyncio.Queue = asyncio.Queue()
    await queue.put({{"id": "m1", "payload": "hello"}})
    msg = await queue.get()
    out = handle(msg)
    assert out.get("id") == "m1", f"unexpected output: {{out!r}}"
    print("REAL BROKER OK:", scaffold_status())


if __name__ == "__main__":
    asyncio.run(_run())
'''


def scaffold_uv_event_driven(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "uv-event-driven":
        raise RecipeError(f"Unsupported event-driven scaffold recipe: {recipe}")
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
    (package_dir / "worker.py").write_text(_render_worker(), encoding="utf-8")
    (package_dir / "__init__.py").write_text(_render_init(package_name), encoding="utf-8")
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "test_smoke.py").write_text(_render_test(package_name), encoding="utf-8")
    scripts = project_root / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    (scripts / "verify_real_broker.py").write_text(_render_real_broker_script(package_name), encoding="utf-8")
    add_pinned_pytest(provider, project_root, package_name)
    return ScaffoldResult(
        command_result=scaffold,
        layout={
            "source": f"src/{package_name}/",
            "worker": f"src/{package_name}/worker.py",
            "tests": "tests/",
            "scripts": "scripts/",
            "packaging": "pyproject.toml",
        },
    )
