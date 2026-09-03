from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator


PACKAGE_ROOT = Path(__file__).resolve().parent
DEFAULT_BLUEPRINT_SCHEMA = PACKAGE_ROOT / "schema_data" / "blueprint.schema.json"
DEFAULT_META_SCHEMA = PACKAGE_ROOT / "schema_data" / "blueprint-meta.schema.json"


@dataclass(frozen=True)
class ValidationIssue:
    document: str
    path: str
    message: str


@dataclass(frozen=True)
class ValidationResult:
    structure_status: str
    readiness_status: str | None
    issues: tuple[ValidationIssue, ...]

    @property
    def is_structurally_valid(self) -> bool:
        return self.structure_status == "STRUCTURALLY_VALID"

    @property
    def is_usable(self) -> bool:
        return self.readiness_status == "USABLE"

    def to_dict(self) -> dict[str, Any]:
        return {
            "structure_status": self.structure_status,
            "readiness_status": self.readiness_status,
            "issues": [asdict(issue) for issue in self.issues],
        }


def load_document(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _json_path(parts: list[Any]) -> str:
    if not parts:
        return "/"
    encoded = []
    for part in parts:
        text = str(part).replace("~", "~0").replace("/", "~1")
        encoded.append(text)
    return "/" + "/".join(encoded)


def _schema_issues(document_name: str, document: Any, schema: dict[str, Any]) -> list[ValidationIssue]:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(document), key=lambda err: list(err.absolute_path))
    return [
        ValidationIssue(
            document=document_name,
            path=_json_path(list(error.absolute_path)),
            message=error.message,
        )
        for error in errors
    ]


def _readiness_from_meta(meta: dict[str, Any] | None) -> str:
    if not meta:
        return "USABLE"

    unresolved = meta.get("unresolved") or []
    if any(item.get("blocking") is True for item in unresolved):
        return "BLOCKED"
    if any(item.get("resolution_required") is True for item in unresolved):
        return "NEEDS_RESOLUTION"
    return "USABLE"


def validate_blueprint(
    blueprint: Any,
    meta: Any | None = None,
    *,
    blueprint_schema: dict[str, Any] | None = None,
    meta_schema: dict[str, Any] | None = None,
) -> ValidationResult:
    blueprint_schema = blueprint_schema or load_json(DEFAULT_BLUEPRINT_SCHEMA)
    meta_schema = meta_schema or load_json(DEFAULT_META_SCHEMA)

    issues = _schema_issues("blueprint", blueprint, blueprint_schema)
    if meta is not None:
        issues.extend(_schema_issues("metadata", meta, meta_schema))

    if issues:
        return ValidationResult(
            structure_status="INVALID",
            readiness_status=None,
            issues=tuple(issues),
        )

    return ValidationResult(
        structure_status="STRUCTURALLY_VALID",
        readiness_status=_readiness_from_meta(meta),
        issues=(),
    )


def validate_files(blueprint_path: Path, meta_path: Path | None = None) -> ValidationResult:
    blueprint = load_document(blueprint_path)
    meta = load_document(meta_path) if meta_path else None
    return validate_blueprint(blueprint, meta)


def _exit_code(result: ValidationResult) -> int:
    if result.structure_status != "STRUCTURALLY_VALID":
        return 1
    if result.readiness_status == "USABLE":
        return 0
    if result.readiness_status == "NEEDS_RESOLUTION":
        return 2
    if result.readiness_status == "BLOCKED":
        return 3
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a Project Blueprint V0.1")
    parser.add_argument("blueprint", type=Path)
    parser.add_argument("--meta", type=Path, default=None)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    result = validate_files(args.blueprint, args.meta)
    if args.as_json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(f"structure_status: {result.structure_status}")
        print(f"readiness_status: {result.readiness_status or '-'}")
        for issue in result.issues:
            print(f"{issue.document}{issue.path}: {issue.message}")
    return _exit_code(result)


if __name__ == "__main__":
    raise SystemExit(main())
