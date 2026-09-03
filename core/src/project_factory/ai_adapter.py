from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .semantic import SemanticAdapterError, SemanticProposal, SemanticSupport


_SYSTEM_PROMPT = r'''You are the optional semantic assistant for Project Factory.
Turn the user's REDACTED project request into a conservative Blueprint proposal.
You are advisory only. Never invent repository facts, credentials, provider availability, or execution success.
Return one JSON object with exactly these top-level fields:
- blueprint: Project Factory Blueprint schema 0.1 candidate
- metadata: {"schema_version":"0.1","provenance":{JSON_POINTER:{"source":"EXPLICIT|INFERRED|DEFAULT","note"?:string}}}
- questions: string[]
- support: [{"path":JSON_POINTER,"source":"EXPLICIT|INFERRED|DEFAULT","evidence_text"?:string,"reason"?:string}]
Rules:
1. Every metadata.provenance path must have one matching support entry.
2. EXPLICIT/INFERRED evidence_text must be an exact substring of the user's request.
3. INFERRED/DEFAULT support must include a reason.
4. Never use DETECTED; text-only input cannot prove repository facts.
5. Prefer unresolved questions instead of guessing when project type, platform, or hard constraints are ambiguous.
6. Do not select a Project Factory profile/provider directly; the deterministic registry does that after validation.
7. Never reproduce secret values; the input may contain [REDACTED_SECRET].
'''


@dataclass(frozen=True)
class AIEndpointConfig:
    endpoint: str
    model: str
    api_key_env: str = ""
    timeout_seconds: float = 45.0

    def validate(self) -> None:
        if not self.endpoint.startswith(("http://", "https://")):
            raise ValueError("AI endpoint must start with http:// or https://")
        if not str(self.model or "").strip():
            raise ValueError("AI model must not be empty.")
        if not (1 <= float(self.timeout_seconds) <= 300):
            raise ValueError("AI timeout must be between 1 and 300 seconds.")


class OpenAICompatibleSemanticAdapter:
    """Optional HTTP semantic assistant using a Chat-Completions-compatible endpoint.

    The adapter is deliberately provider-neutral.  The endpoint/model are user settings;
    credentials are read from an environment-variable name and are never persisted here.
    All returned claims still pass SemanticAdapter provenance, redaction and Blueprint gates.
    """

    id = "openai-compatible-json"
    version = "0.1"
    trust_class = "external-semantic"

    def __init__(self, config: AIEndpointConfig) -> None:
        config.validate()
        self.config = config

    def _is_ollama(self) -> bool:
        endpoint = self.config.endpoint.casefold()
        return "11434" in endpoint or "ollama" in endpoint

    def _request_url(self) -> str:
        if not self._is_ollama():
            return self.config.endpoint
        base = self.config.endpoint.split("/v1", 1)[0].split("/api", 1)[0].rstrip("/")
        return base + "/api/chat"

    def _request_body(self, text: str) -> bytes:
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ]
        if self._is_ollama():
            payload = {
                "model": self.config.model,
                "messages": messages,
                "stream": False,
                "format": "json",
            }
        else:
            payload = {
                "model": self.config.model,
                "messages": messages,
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
            }
        return json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        env_name = str(self.config.api_key_env or "").strip()
        # Local Ollama endpoints have no credential surface at all.  Requiring an
        # API key here only produced bogus "OPENAI_API_KEY is not set" failures on
        # a fully local setup, so credentials are skipped for them.
        if self._is_ollama():
            return headers
        if env_name:
            value = os.environ.get(env_name, "")
            if not value:
                raise SemanticAdapterError(f"AI credential environment variable {env_name!r} is not set.")
            headers["Authorization"] = f"Bearer {value}"
        return headers

    def probe(self, probe_seconds: float = 8.0) -> None:
        """Cheap liveness + contract check before a real request is made.

        External semantic adapters must return provenance-complete proposals; a local
        model that answers loosely would otherwise fail mid-generation and take the
        whole build down with it.  Probing first lets callers degrade to the
        deterministic intake instead.
        """
        import dataclasses

        from .validator import validate_blueprint

        # AIEndpointConfig is frozen, so probe with a temporary short-timeout clone
        # instead of mutating the live config.
        if probe_seconds and probe_seconds != self.config.timeout_seconds:
            prober = OpenAICompatibleSemanticAdapter(
                dataclasses.replace(self.config, timeout_seconds=probe_seconds)
            )
        else:
            prober = self
        proposal = prober.propose("probe")
        validate_blueprint(proposal.blueprint, proposal.metadata)

    def propose(self, text: str) -> SemanticProposal:
        request = Request(
            self._request_url(),
            data=self._request_body(text),
            headers=self._headers(),
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.config.timeout_seconds) as response:  # noqa: S310 - endpoint is user configured
                raw = response.read(2 * 1024 * 1024 + 1)
        except HTTPError as exc:
            raise SemanticAdapterError(f"AI endpoint returned HTTP {exc.code}.") from exc
        except URLError as exc:
            raise SemanticAdapterError(f"AI endpoint is unreachable: {exc.reason}") from exc
        except TimeoutError as exc:
            raise SemanticAdapterError("AI endpoint timed out.") from exc
        if len(raw) > 2 * 1024 * 1024:
            raise SemanticAdapterError("AI response exceeds the 2 MiB safety limit.")
        try:
            envelope = json.loads(raw.decode("utf-8"))
            if isinstance(envelope, dict) and "choices" in envelope:
                content = envelope["choices"][0]["message"]["content"]
            elif isinstance(envelope, dict) and "message" in envelope:
                content = envelope["message"]["content"]
            else:
                raise KeyError("choices")
            payload = json.loads(content) if isinstance(content, str) else content
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise SemanticAdapterError("AI endpoint did not return the expected JSON chat-completions envelope.") from exc
        if not isinstance(payload, dict):
            raise SemanticAdapterError("AI semantic payload must be a JSON object.")
        try:
            blueprint = payload["blueprint"]
            metadata = payload["metadata"]
            questions = tuple(str(item) for item in payload.get("questions", []) or [])
            support = tuple(
                SemanticSupport(
                    path=str(item["path"]),
                    source=str(item["source"]),
                    evidence_text=(str(item["evidence_text"]) if item.get("evidence_text") is not None else None),
                    reason=(str(item["reason"]) if item.get("reason") is not None else None),
                )
                for item in payload.get("support", []) or []
            )
        except (KeyError, TypeError) as exc:
            raise SemanticAdapterError("AI semantic payload is missing required proposal fields.") from exc
        if not isinstance(blueprint, dict) or not isinstance(metadata, dict):
            raise SemanticAdapterError("AI blueprint and metadata must be JSON objects.")
        return SemanticProposal(blueprint=blueprint, metadata=metadata, questions=questions, support=support)
