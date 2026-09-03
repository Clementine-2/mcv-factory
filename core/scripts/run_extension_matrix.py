from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from project_factory.extensions import (  # noqa: E402
    apply_extension_plan,
    load_extension_runtime,
    plan_add_extension,
    sha256_file,
)
from project_factory.factory import generate_project, restore_verify_project_zip, write_project_manifest  # noqa: E402
from project_factory.ownership import collect_managed_file_hashes, managed_paths_from_lock, write_factory_overlay_manifest  # noqa: E402
from project_factory.upgrade import apply_upgrade, plan_upgrade, rollback_upgrade  # noqa: E402

DECLARATIVE = ROOT / "fixtures/extensions/team-standard/extension.yaml"
TRUSTED = ROOT / "fixtures/extensions/trusted-lab/extension.yaml"


def add(state: Path, manifest: Path, *, trust_code: bool = False) -> None:
    plan = plan_add_extension(state, manifest, trust_code=trust_code)
    apply_extension_plan(state, plan, confirm_plan_sha256=plan.plan_sha256)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run P9 declarative/trusted extension Golden and migration matrix")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    args = parser.parse_args()
    work = args.output_dir.resolve()
    if work.exists() and any(work.iterdir()):
        raise SystemExit(f"Refusing to overwrite non-empty extension matrix directory: {work}")
    work.mkdir(parents=True, exist_ok=True)

    records = []
    for label, manifest, trust_code in (
        ("declarative", DECLARATIVE, False),
        ("trusted-code", TRUSTED, True),
    ):
        case = work / label
        case.mkdir()
        state = case / "extensions.json"
        add(state, manifest, trust_code=trust_code)
        result = generate_project("做一个 Python CLI 工具。", f"p9-{label}-cli", case / "out", extension_set=state)
        verify = restore_verify_project_zip(result.project_zip, extension_set=state)
        lock = json.loads((result.project_root / "project.lock.json").read_text(encoding="utf-8"))
        receipt = lock["extensions"][0]
        records.append({
            "case": label,
            "project": result.project_root.name,
            "profile": result.profile.profile_id,
            "provider": result.provider.provider_id,
            "extension_id": receipt["id"],
            "extension_version": receipt["version"],
            "trust": receipt["trust"],
            "distribution": receipt.get("distribution"),
            "distribution_version": receipt.get("distribution_version"),
            "distribution_sha256": receipt.get("distribution_sha256"),
            "artifact_count": len(lock.get("extension_artifacts", [])),
            "restore_status": verify["status"],
        })

    # Migration proof uses an explicitly labelled synthetic v1 project state.
    migration = work / "trusted-migration"
    migration.mkdir()
    state = migration / "extensions.json"
    add(state, TRUSTED, trust_code=True)
    result = generate_project("做一个 Python CLI 工具。", "p9-trusted-migrate", migration / "out", extension_set=state)
    project = result.project_root
    version_file = project / ".project/extensions/trusted-lab/version.txt"
    version_file.write_text("1.0.0\n", encoding="utf-8")
    receipt_path = project / ".project/extensions.lock.json"
    receipt_doc = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt_doc["extensions"][0]["version"] = "1.0.0"
    for artifact in receipt_doc["artifacts"]:
        if artifact["path"].endswith("/version.txt"):
            artifact["sha256"] = sha256_file(version_file)
    receipt_path.write_text(json.dumps(receipt_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lock_path = project / "project.lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    lock["extensions"][0]["version"] = "1.0.0"
    for artifact in lock["extension_artifacts"]:
        if artifact["path"].endswith("/version.txt"):
            artifact["sha256"] = sha256_file(version_file)
    lock["managed_files"] = collect_managed_file_hashes(project, managed_paths_from_lock(lock))
    lock_path.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_factory_overlay_manifest(project, list(managed_paths_from_lock(lock)) + ["project.lock.json"])
    write_project_manifest(project)

    plan = plan_upgrade(project, extension_set=state)
    if plan.status != "READY":
        raise SystemExit(f"trusted migration DryRun not READY: {plan.blocked_reasons}")
    extension_changes = [item.path for item in plan.changes if "trusted-lab" in item.path and item.action != "UNCHANGED"]
    if extension_changes != [".project/extensions/trusted-lab/version.txt"]:
        raise SystemExit(f"Unexpected extension migration targets: {extension_changes!r}")
    applied = apply_upgrade(project, confirm_plan_sha256=plan.plan_sha256, extension_set=state)
    if version_file.read_text(encoding="utf-8") != "2.0.0\n":
        raise SystemExit("Extension migration did not update scoped version marker")
    rolled = rollback_upgrade(project, Path(applied["rollback_bundle"]), confirm_bundle_sha256=applied["rollback_bundle_sha256"])
    if version_file.read_text(encoding="utf-8") != "1.0.0\n":
        raise SystemExit("Extension rollback did not restore synthetic v1 marker")

    evidence = {
        "status": "PASS",
        "goldens": records,
        "migration": {
            "fixture_kind": "synthetic-v1-state-derived-from-v2-golden",
            "dry_run_status": plan.status,
            "scoped_changes": extension_changes,
            "apply_status": applied["status"],
            "rollback_status": rolled["status"],
            "scope_rule": ".project/extensions/trusted-lab/** only",
        },
    }
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
