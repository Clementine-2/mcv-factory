from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from project_factory.factory import generate_project
from project_factory.normalizer import normalize_requirement


class E02CombinationGuardTests(unittest.TestCase):
    def test_http_with_celery_stays_http_service(self) -> None:
        req = "做一个 Python FastAPI HTTP 服务，使用 Celery 处理后台任务。"
        result = normalize_requirement(req)
        kinds = {p["kind"] for p in result.blueprint["work_products"]}
        # Should be service/http-service, not event-driven
        self.assertIn("service", kinds)
        self.assertNotIn("event-driven-app", kinds)
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            gen = generate_project(req, "e02-http-celery", out)
            self.assertEqual(gen.profile.profile_id, "python-http-service")

    def test_otel_in_library_stays_library(self) -> None:
        req = "做一个 Python library，使用 OpenTelemetry 提供追踪工具。"
        result = normalize_requirement(req)
        kinds = {p["kind"] for p in result.blueprint["work_products"]}
        self.assertIn("library", kinds)
        self.assertNotIn("observability-agent", kinds)
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            gen = generate_project(req, "e02-otel-lib", out)
            self.assertEqual(gen.profile.profile_id, "python-library")

    def test_pure_otel_collector_is_observability(self) -> None:
        req = "做一个 OpenTelemetry collector 配置/探针项目。"
        result = normalize_requirement(req)
        kinds = {p["kind"] for p in result.blueprint["work_products"]}
        self.assertIn("observability-agent", kinds)
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            gen = generate_project(req, "e02-otel-probe", out)
            self.assertEqual(gen.profile.profile_id, "python-observability")


class E03CSharpGuardTests(unittest.TestCase):
    def test_csharp_library_recognized_without_wpf(self) -> None:
        for text in [
            "做一个 C# library",
            "做一个 C# library 提供字符串工具",
            "Create a C# library for utilities",
            "做一个 csharp library",
        ]:
            with self.subTest(text=text):
                result = normalize_requirement(text)
                kinds = {p["kind"] for p in result.blueprint["work_products"]}
                self.assertIn("library", kinds)
                tech = result.blueprint.get("technology", {}).get("required", [])
                self.assertIn("csharp", [t.lower() for t in tech])
                # Generate should pick csharp-library, not python
                with tempfile.TemporaryDirectory() as td:
                    out = Path(td)
                    gen = generate_project(text, "e03-cs-lib", out)
                    self.assertEqual(gen.profile.profile_id, "csharp-library")

    def test_csharp_library_next_steps_mentions_dotnet(self) -> None:
        from project_factory.assembly import profile_next_steps

        nxt = profile_next_steps("csharp-library")
        self.assertIn("dotnet", nxt.lower())
        self.assertIn("xunit", nxt.lower())


if __name__ == "__main__":
    unittest.main()
