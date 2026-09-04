"""OpenTelemetry in-memory probe on the uv language root.

A collector / sidecar process is not a verification gate.
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

OTEL_API_PIN = "1.31.1"
OTEL_SDK_PIN = "1.31.1"


def _render_probe() -> str:
    return '''from __future__ import annotations

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


def scaffold_status() -> str:
    return "observability probe scaffold ready"


def record_status() -> list[str]:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("scaffold")
    with tracer.start_as_current_span("scaffold.status") as span:
        span.set_attribute("status", scaffold_status())
    return [item.name for item in exporter.get_finished_spans()]


def record_event(name: str, attributes: dict[str, str]) -> list[dict[str, str]]:
    """真实可运行的示例：记录一个带属性的 span 并返回快照。"""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("scaffold.demo")
    with tracer.start_as_current_span(name) as span:
        for key, value in attributes.items():
            span.set_attribute(key, value)
    return [
        {"name": item.name, "attributes": dict(item.attributes)}
        for item in exporter.get_finished_spans()
    ]
'''


def _render_init(package_name: str) -> str:
    return f'''from __future__ import annotations

from {package_name}.probe import record_event, record_status, scaffold_status

__version__ = "0.1.0"
__all__ = ["record_event", "record_status", "scaffold_status", "__version__"]
'''


def _render_test(package_name: str) -> str:
    return f'''from __future__ import annotations

import unittest

from {package_name}.probe import record_status, scaffold_status


class SmokeTest(unittest.TestCase):
    def test_in_memory_span(self) -> None:
        names = record_status()
        self.assertEqual(names, ["scaffold.status"])
        self.assertEqual(scaffold_status(), "observability probe scaffold ready")


if __name__ == "__main__":
    unittest.main()
'''


def _render_demo_test(package_name: str) -> str:
    return f'''from __future__ import annotations

import unittest

from {package_name}.probe import record_event


class DemoTest(unittest.TestCase):
    def test_record_event_captures_name(self) -> None:
        spans = record_event("demo.request", {{"method": "GET"}})
        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0]["name"], "demo.request")

    def test_record_event_captures_attributes(self) -> None:
        spans = record_event("demo.request", {{"method": "GET"}})
        self.assertEqual(spans[0]["attributes"]["method"], "GET")


if __name__ == "__main__":
    unittest.main()
'''


def scaffold_uv_observability(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "uv-observability":
        raise RecipeError(f"Unsupported observability scaffold recipe: {recipe}")
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
        [
            provider.executable,
            "add",
            f"opentelemetry-api=={OTEL_API_PIN}",
            f"opentelemetry-sdk=={OTEL_SDK_PIN}",
        ],
        project_root,
        timeout=600,
    )
    package_dir = project_root / "src" / package_name
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "probe.py").write_text(_render_probe(), encoding="utf-8")
    (package_dir / "__init__.py").write_text(_render_init(package_name), encoding="utf-8")
    tests = project_root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "test_smoke.py").write_text(_render_test(package_name), encoding="utf-8")
    (tests / "test_demo.py").write_text(_render_demo_test(package_name), encoding="utf-8")
    add_pinned_pytest(provider, project_root, package_name)
    return ScaffoldResult(
        command_result=scaffold,
        layout={
            "source": f"src/{package_name}/",
            "probe": f"src/{package_name}/probe.py",
            "tests": "tests/",
            "packaging": "pyproject.toml",
        },
    )
