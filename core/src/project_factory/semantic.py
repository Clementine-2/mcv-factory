from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Protocol

from .normalizer import NormalizationResult, normalize_requirement, redact_secrets
from .validator import ValidationResult, validate_blueprint


class SemanticAdapterError(RuntimeError):
    """Raised when a semantic adapter violates the intake contract."""


@dataclass(frozen=True)
class SemanticSupport:
    path: str
    source: str
    evidence_text: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class SemanticProposal:
    blueprint: dict[str, Any]
    metadata: dict[str, Any]
    questions: tuple[str, ...] = ()
    support: tuple[SemanticSupport, ...] = ()


class SemanticAdapter(Protocol):
    id: str
    version: str
    trust_class: str

    def propose(self, text: str) -> SemanticProposal:
        ...


@dataclass(frozen=True)
class SemanticIntakeResult:
    blueprint: dict[str, Any]
    metadata: dict[str, Any]
    validation: ValidationResult
    questions: tuple[str, ...]
    receipt: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "blueprint": self.blueprint,
            "metadata": self.metadata,
            "validation": self.validation.to_dict(),
            "questions": list(self.questions),
            "receipt": self.receipt,
        }


class DeterministicSemanticAdapter:
    id = "deterministic-baseline"
    version = "0.2"
    trust_class = "deterministic-baseline"

    def propose(self, text: str) -> SemanticProposal:
        result: NormalizationResult = normalize_requirement(text)
        return SemanticProposal(
            blueprint=result.blueprint,
            metadata=result.metadata,
            questions=result.questions,
        )


class UserConfirmedSemanticAdapter:
    """Adapter for structured Blueprint values explicitly confirmed in the UX layer.

    This adapter never calls a model or network service.  It exists so the Requirement
    Studio can let a user edit a structured matrix, preview it, then pass the exact
    confirmed Blueprint through the same schema/readiness gates as every other intake.
    """

    id = "user-confirmed-matrix"
    version = "0.1"
    trust_class = "user-confirmed"

    def __init__(
        self,
        blueprint: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        questions: tuple[str, ...] | list[str] = (),
    ) -> None:
        self._blueprint = copy.deepcopy(blueprint)
        self._metadata = copy.deepcopy(metadata or {"schema_version": "0.1"})
        self._questions = tuple(questions)

    def propose(self, text: str) -> SemanticProposal:
        del text
        return SemanticProposal(
            blueprint=copy.deepcopy(self._blueprint),
            metadata=copy.deepcopy(self._metadata),
            questions=self._questions,
        )


def _deep_redact(value: Any) -> tuple[Any, int]:
    if isinstance(value, str):
        redacted, changed = redact_secrets(value)
        return redacted, int(changed)
    if isinstance(value, list):
        out: list[Any] = []
        count = 0
        for item in value:
            cleaned, item_count = _deep_redact(item)
            out.append(cleaned)
            count += item_count
        return out, count
    if isinstance(value, tuple):
        cleaned_list, count = _deep_redact(list(value))
        return tuple(cleaned_list), count
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        count = 0
        for key, item in value.items():
            cleaned, item_count = _deep_redact(item)
            out[str(key)] = cleaned
            count += item_count
        return out, count
    return copy.deepcopy(value), 0


def _questions_from_meta(meta: dict[str, Any]) -> tuple[str, ...]:
    questions: list[str] = []
    for item in meta.get("unresolved", []) or []:
        if not item.get("resolution_required"):
            continue
        path = str(item.get("path", "/"))
        if path == "/work_products/0/kind":
            questions.append(
                "What kind of deliverable should this be (for example CLI, web app, mobile app, desktop app, library, or research artifact)?"
            )
        elif path == "/targets":
            questions.append("Which target platform(s) are required?")
        else:
            questions.append(f"Please resolve the requirement at {path}: {item.get('reason', 'required information is missing')}")
    return tuple(dict.fromkeys(questions))


def _validate_external_support(
    source_text: str,
    metadata: dict[str, Any],
    support: tuple[SemanticSupport, ...],
) -> None:
    support_by_path: dict[str, SemanticSupport] = {}
    for item in support:
        if not item.path.startswith("/"):
            raise SemanticAdapterError(f"Semantic support path must be a JSON Pointer: {item.path!r}.")
        if item.path in support_by_path:
            raise SemanticAdapterError(f"Duplicate semantic support path: {item.path!r}.")
        support_by_path[item.path] = item

    provenance = metadata.get("provenance", {}) or {}
    for path, record in provenance.items():
        item = support_by_path.get(path)
        if item is None:
            raise SemanticAdapterError(f"External semantic adapter omitted support for provenance path {path!r}.")
        source = str(record.get("source"))
        if item.source != source:
            raise SemanticAdapterError(
                f"Semantic support source mismatch at {path!r}: metadata={source!r}, support={item.source!r}."
            )
        if source == "DETECTED":
            raise SemanticAdapterError(
                "Text-only external semantic adapters may not claim DETECTED facts; repository detection requires a separate evidence channel."
            )
        if source in {"EXPLICIT", "INFERRED"}:
            if not item.evidence_text:
                raise SemanticAdapterError(f"{source} semantic support at {path!r} requires evidence_text.")
            evidence, _ = redact_secrets(item.evidence_text)
            source_safe, _ = redact_secrets(source_text)
            if evidence.casefold() not in source_safe.casefold():
                raise SemanticAdapterError(
                    f"Semantic support evidence_text for {path!r} is not present in the source requirement."
                )
        if source in {"INFERRED", "DEFAULT"} and not item.reason:
            raise SemanticAdapterError(f"{source} semantic support at {path!r} requires a reason.")

    unexpected = sorted(set(support_by_path) - set(provenance))
    if unexpected:
        raise SemanticAdapterError(
            "Semantic support references paths with no matching provenance record: " + ", ".join(unexpected)
        )


def run_semantic_intake(text: str, adapter: SemanticAdapter | None = None) -> SemanticIntakeResult:
    normalized_text = " ".join(text.strip().split())
    if not normalized_text:
        raise ValueError("Requirement text must not be empty.")

    adapter = adapter or DeterministicSemanticAdapter()

    # External semantic services must never receive raw secret material.  Keep the
    # digest over the normalized source for audit continuity, but hand external
    # adapters only the redacted view.  Deterministic/user-confirmed adapters stay
    # local and can safely receive the normalized text.
    adapter_input = normalized_text
    input_redactions = 0
    if adapter.trust_class == "external-semantic":
        adapter_input, input_changed = redact_secrets(normalized_text)
        input_redactions = int(input_changed)
    proposal = adapter.propose(adapter_input)

    cleaned_blueprint, blueprint_redactions = _deep_redact(proposal.blueprint)
    cleaned_metadata, metadata_redactions = _deep_redact(proposal.metadata)
    cleaned_questions, question_redactions = _deep_redact(list(proposal.questions))
    cleaned_support_raw, support_redactions = _deep_redact(
        [
            {
                "path": item.path,
                "source": item.source,
                "evidence_text": item.evidence_text,
                "reason": item.reason,
            }
            for item in proposal.support
        ]
    )
    cleaned_support = tuple(SemanticSupport(**item) for item in cleaned_support_raw)

    if adapter.trust_class == "external-semantic":
        _validate_external_support(adapter_input, cleaned_metadata, cleaned_support)
    elif adapter.trust_class not in {"deterministic-baseline", "user-confirmed"}:
        raise SemanticAdapterError(f"Unknown semantic adapter trust_class: {adapter.trust_class!r}.")

    validation = validate_blueprint(cleaned_blueprint, cleaned_metadata)
    questions = tuple(cleaned_questions) or _questions_from_meta(cleaned_metadata)
    redaction_count = input_redactions + blueprint_redactions + metadata_redactions + question_redactions + support_redactions
    receipt = {
        "adapter": {
            "id": adapter.id,
            "version": adapter.version,
            "trust_class": adapter.trust_class,
        },
        "source_requirement_sha256": hashlib.sha256(normalized_text.encode("utf-8")).hexdigest(),
        "guard": {
            "status": "PASS",
            "secret_redactions": redaction_count,
            "schema_status": validation.structure_status,
            "readiness_status": validation.readiness_status,
        },
        "support": [
            {
                "path": item.path,
                "source": item.source,
                **({"evidence_text": item.evidence_text} if item.evidence_text else {}),
                **({"reason": item.reason} if item.reason else {}),
            }
            for item in cleaned_support
        ],
    }
    return SemanticIntakeResult(
        blueprint=cleaned_blueprint,
        metadata=cleaned_metadata,
        validation=validation,
        questions=questions,
        receipt=receipt,
    )


def receipt_json(result: SemanticIntakeResult) -> str:
    return json.dumps(result.receipt, ensure_ascii=False, sort_keys=True)


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Run guarded semantic intake through the default Semantic Adapter")
    parser.add_argument("text", nargs="?", help="Natural-language project requirement. If omitted, read stdin.")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    text = args.text if args.text is not None else sys.stdin.read()
    try:
        result = run_semantic_intake(text)
    except (ValueError, SemanticAdapterError) as exc:
        payload = {"status": "INVALID", "error": str(exc)}
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.as_json else f"error: {exc}")
        return 1
    if args.as_json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"structure_status: {result.validation.structure_status}")
        print(f"readiness_status: {result.validation.readiness_status or '-'}")
        print(f"semantic_adapter: {result.receipt['adapter']['id']}@{result.receipt['adapter']['version']}")
        for question in result.questions:
            print(f"question: {question}")
    if result.validation.structure_status != "STRUCTURALLY_VALID":
        return 1
    if result.validation.readiness_status == "USABLE":
        return 0
    if result.validation.readiness_status == "NEEDS_RESOLUTION":
        return 2
    if result.validation.readiness_status == "BLOCKED":
        return 3
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
