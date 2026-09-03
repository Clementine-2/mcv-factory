from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from .extensions import verify_extension_receipt
from .factory import (
    FACTORY_STAGE,
    FACTORY_VERSION,
    FactoryError,
    generate_project,
    restore_verify_project_zip,
    verify_project_manifest,
)
from .harness import verify_harness_contracts
from .host import verify_host_materialization
from .ownership import verify_factory_overlay_manifest
from .process import verify_process_materialization
from .product import doctor
from .runner import verify_runner_materialization


class UXError(RuntimeError):
    """Raised for bounded, human-facing command errors."""


def _print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def _status_line(value: str) -> str:
    return "OK" if value in {"PASS", "VERIFIED", "PARTIALLY_VERIFIED", "NOT_CONFIGURED"} else value


def check_project(project_root: Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    if not root.is_dir():
        raise UXError(f"Project directory does not exist: {root}")
    lock_path = root / "project.lock.json"
    if not lock_path.is_file():
        files = [path for path in root.rglob("*") if path.is_file()]
        if not files:
            return {"status": "PASS", "kind": "blank", "project": str(root)}
        raise UXError(f"Not a Factory project: project.lock.json is missing in {root}")
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UXError(f"project.lock.json cannot be read safely: {exc}") from exc
    if not isinstance(lock, dict):
        raise UXError("project.lock.json must contain a JSON object.")

    manifest_ok, manifest_failures = verify_project_manifest(root)
    overlay_ok, overlay_failures = verify_factory_overlay_manifest(root)

    harness = verify_harness_contracts(root, lock.get("harness_contract", {}))
    host = verify_host_materialization(root, lock.get("host_integration"))
    runner = verify_runner_materialization(root, lock.get("runner_integration"))
    process = verify_process_materialization(root, lock.get("process_integration"))

    extension_receipt_path = root / ".project" / "extensions.lock.json"
    if extension_receipt_path.is_file():
        try:
            extension_receipt = json.loads(extension_receipt_path.read_text(encoding="utf-8"))
            extensions = verify_extension_receipt(root, extension_receipt)
        except (OSError, json.JSONDecodeError) as exc:
            extensions = {"status": "FAILED", "failures": [f"extensions.lock.json unreadable: {exc}"]}
    else:
        extensions = {"status": "FAILED", "failures": [".project/extensions.lock.json is missing"]}

    checks = {
        "project_manifest": {"status": "PASS" if manifest_ok else "FAILED", "failures": manifest_failures},
        "factory_overlay": {"status": "PASS" if overlay_ok else "FAILED", "failures": overlay_failures},
        "harness": harness,
        "host": host,
        "runner": runner,
        "process": process,
        "extensions": extensions,
    }
    failures: list[str] = []
    for check_id, value in checks.items():
        if value.get("status") == "FAILED":
            detail = list(value.get("failures", []))
            failures.append(f"{check_id}: " + ("; ".join(detail) if detail else "failed"))
    return {
        "schema_version": "0.1",
        "status": "PASS" if not failures else "FAILED",
        "project": str(root),
        "project_name": lock.get("project_name"),
        "factory": lock.get("factory", {}),
        "profile": lock.get("profile", {}).get("id"),
        "checks": checks,
        "failures": failures,
        "runtime_execution_performed": False,
    }


def _render_status(report: dict[str, Any]) -> None:
    print(f"Project Factory {FACTORY_VERSION} ({FACTORY_STAGE})")
    print(f"Status: {report['status']}")
    profiles = report.get("ready_profiles", [])
    print("Ready profiles: " + (", ".join(profiles) if profiles else "none"))
    warnings = report.get("warnings", [])
    print(f"Warnings: {len(warnings)}")
    if warnings:
        for warning in warnings[:5]:
            print(f"  - {warning}")
    if report.get("hard_failures"):
        print("Hard failures:")
        for failure in report["hard_failures"]:
            print(f"  - {failure}")
    print("Full diagnostics: project-factory doctor --deep")


def _render_new(result: Any) -> None:
    print(f"Created: {result.project_name}")
    print(f"Project: {result.project_root}")
    print(f"Project ZIP: {result.project_zip}")
    print(f"Profile: {result.profile.profile_id}")
    print(f"Verification: {result.verification['status']}")
    print("Next:")
    print(f"  project-factory check {result.project_root}")
    print(f"  project-factory verify {result.project_zip}")


def _render_check(report: dict[str, Any]) -> None:
    print(f"Project: {report.get('project_name') or Path(report['project']).name}")
    print(f"Status: {report['status']}")
    for name, check in report["checks"].items():
        print(f"  {name}: {_status_line(str(check.get('status', 'UNKNOWN')))}")
    if report["failures"]:
        print("Failures:")
        for failure in report["failures"]:
            print(f"  - {failure}")
    print("Runtime commands executed: no")


def _render_verify(report: dict[str, Any]) -> None:
    print(f"Project: {report.get('project_name', 'unknown')}")
    print(f"Status: {report.get('status', 'UNKNOWN')}")
    print(f"Manifest: {'PASS' if report.get('manifest_verified') else 'FAILED'}")
    verification = report.get("verification", {})
    if verification:
        print(f"Verification suite: {verification.get('suite', {}).get('id', 'unknown')}")
    print(f"ZIP SHA256: {report.get('zip_sha256', 'unknown')}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="project-factory",
        description="Create, inspect and verify Factory projects. Advanced machine commands remain available for automation.",
        epilog=(
            "Common path: status -> new -> check -> verify. "
            "Advanced commands: doctor, bootstrap, generate, restore-verify, checkpoint, upgrade, extension, host, runner, normalize, intake, decide, validate, compatibility."
        ),
    )
    sub = parser.add_subparsers(dest="command")

    status = sub.add_parser("status", help="Show a short readiness summary")
    status.add_argument("--deep", action="store_true", help="Include temporary end-to-end smoke generation")
    status.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    new = sub.add_parser("new", help="Create a verified project with minimal required options")
    new.add_argument("name", help="Project name: letters, digits, '.', '_' or '-'")
    new.add_argument("requirement", nargs="?", default="", help="What the project should be (omit when using --from-spec or --blank)")
    new.add_argument("-o", "--out", type=Path, default=Path("out"), help="Output directory (default: ./out)")
    new.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    new.add_argument("--blank", action="store_true", help="Create an empty directory")
    new.add_argument("--from-spec", type=Path, help="Structured assembly YAML (click-spec or web-AI filled template)")
    new.add_argument("--no-scaffold", action="store_true", help="Do not scaffold language-root files")
    new.add_argument("--no-harness", action="store_true", help="Do not write AGENTS.md/CLAUDE.md (and GEMINI.md/.cursor/rules). Use --harness to select adapters.")
    new.add_argument("--no-overlay", action="store_true", help="Do not write Factory overlay / skills (skills/{profile}/SKILL.md, factory-discipline)")
    new.add_argument("--no-verify", action="store_true", help="Do not run verification gates")
    new.add_argument("--no-readme", action="store_true", help="Do not write README.md")
    new.add_argument(
        "--harness",
        action="append",
        dest="harness_ids",
        metavar="ID",
        help="Harness adapter to materialize (repeatable): codex→AGENTS.md, claude→CLAUDE.md, cursor→.cursor/rules, gemini→GEMINI.md. Default: codex,claude. Use --no-harness to disable all.",
    )
    new.add_argument("--with-compose", action="store_true", help="C04: add Postgres compose.yaml drawing for http-service (docker up UNVERIFIED)")

    tmpl = sub.add_parser("template", help="Export or inspect the web-AI fill-in assembly template")
    tmpl.add_argument("action", choices=("export", "show"), nargs="?", default="export")
    tmpl.add_argument("-o", "--out", type=Path, help="Write the empty template YAML")
    tmpl.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    check = sub.add_parser("check", help="Run read-only integrity checks on a generated project directory")
    check.add_argument("project", type=Path)
    check.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    verify = sub.add_parser("verify", help="Restore a generated project ZIP in a temporary directory and rerun required verification")
    verify.add_argument("zip_path", type=Path)
    verify.add_argument("--extension-set", type=Path, help="Extension Set required by the locked project")
    verify.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    try:
        if args.command == "status":
            report = doctor(deep=args.deep)
            _print_json(report) if args.json else _render_status(report)
            return 0 if report["status"] != "BLOCKED" else 4
        if args.command == "template":
            from .template import export_template

            payload = export_template(args.out)
            if args.json:
                _print_json(payload)
            else:
                print(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True))
            return 0
        if args.command == "new":
            from .assembly import AssemblyOptions
            from .template import load_template, options_from_template

            spec = load_template(args.from_spec) if args.from_spec else None
            if args.blank:
                options = AssemblyOptions(False, False, False, False, False, (), False)
            elif spec is not None and not any(
                (args.no_scaffold, args.no_harness, args.no_overlay, args.no_verify, args.no_readme, args.harness_ids, args.with_compose)
            ):
                options = None
            else:
                base_options = options_from_template(spec) if spec is not None else None
                options = AssemblyOptions(
                    scaffold=not args.no_scaffold,
                    verification=not args.no_verify,
                    overlay=not args.no_overlay,
                    harness=not args.no_harness,
                    readme=not args.no_readme,
                    harness_ids=tuple(args.harness_ids) if args.harness_ids else (base_options.harness_ids if base_options else None),
                    with_compose=bool(args.with_compose or (base_options.with_compose if base_options else False)),
                )
            result = generate_project(args.requirement, args.name, args.out, options=options, spec=spec)
            if args.json:
                _print_json(
                    {
                        "status": result.verification["status"],
                        "project_name": result.project_name,
                        "project": str(result.project_root),
                        "zip": str(result.project_zip),
                        "profile": result.profile.profile_id,
                    }
                )
            else:
                _render_new(result)
            return 0
        if args.command == "check":
            if args.project.is_file() and args.project.suffix.casefold() == ".zip":
                raise UXError("check expects a project directory; use 'project-factory verify <project.zip>' for a ZIP.")
            report = check_project(args.project)
            _print_json(report) if args.json else _render_check(report)
            return 0 if report["status"] == "PASS" else 4
        if args.command == "verify":
            report = restore_verify_project_zip(args.zip_path, extension_set=args.extension_set)
            _print_json(report) if args.json else _render_verify(report)
            return 0
    except (FactoryError, UXError, OSError, ValueError) as exc:
        if getattr(args, "json", False):
            _print_json({"status": "BLOCKED", "error": str(exc)})
        else:
            print(f"BLOCKED: {exc}")
        return 4
    return 4
