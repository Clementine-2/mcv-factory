from __future__ import annotations

import io
import json
import os
import unittest
from unittest.mock import patch

from project_factory.ai_adapter import AIEndpointConfig, OpenAICompatibleSemanticAdapter
from project_factory.semantic import run_semantic_intake


class _Response:
    def __init__(self, payload: dict) -> None:
        self._data = json.dumps(payload).encode()
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, limit: int) -> bytes:
        return self._data[:limit]


class AIAdapterTests(unittest.TestCase):
    def test_mocked_external_ai_is_advisory_and_auditable(self) -> None:
        requirement = "Build a Python CLI for local text cleanup."
        semantic_payload = {
            "blueprint": {
                "schema_version": "0.1",
                "project": {"purpose": requirement},
                "work_products": [{"kind": "cli"}],
                "technology": {"required": ["python"]},
            },
            "metadata": {
                "schema_version": "0.1",
                "provenance": {
                    "/project/purpose": {"source": "EXPLICIT"},
                    "/work_products/0/kind": {"source": "INFERRED"},
                    "/technology/required/0": {"source": "EXPLICIT"},
                },
            },
            "questions": [],
            "support": [
                {"path": "/project/purpose", "source": "EXPLICIT", "evidence_text": requirement},
                {"path": "/work_products/0/kind", "source": "INFERRED", "evidence_text": "CLI", "reason": "CLI wording"},
                {"path": "/technology/required/0", "source": "EXPLICIT", "evidence_text": "Python"},
            ],
        }
        envelope = {"choices": [{"message": {"content": json.dumps(semantic_payload)}}]}
        config = AIEndpointConfig("http://127.0.0.1:1234/v1/chat/completions", "local-model")
        adapter = OpenAICompatibleSemanticAdapter(config)
        with patch("project_factory.ai_adapter.urlopen", return_value=_Response(envelope)):
            result = run_semantic_intake(requirement, adapter)
        self.assertEqual(result.validation.readiness_status, "USABLE")
        self.assertEqual(result.receipt["adapter"]["trust_class"], "external-semantic")

    def test_api_key_is_read_from_environment_not_config_value(self) -> None:
        config = AIEndpointConfig("http://localhost/v1/chat/completions", "model", api_key_env="PF_TEST_KEY")
        adapter = OpenAICompatibleSemanticAdapter(config)
        with patch.dict(os.environ, {"PF_TEST_KEY": "super-secret"}, clear=False):
            headers = adapter._headers()
        self.assertEqual(headers["Authorization"], "Bearer super-secret")
        self.assertNotIn("super-secret", repr(config))


if __name__ == "__main__":
    unittest.main()
