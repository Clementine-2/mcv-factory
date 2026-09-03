from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from project_factory.ownership import verify_factory_overlay_manifest  # noqa: E402
from project_factory.upgrade import apply_upgrade, plan_upgrade, rollback_upgrade  # noqa: E402

CASES = ("json-batch-cli", "text-normalizer-lib", "string-tools-js", "cross-browser-helper")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot(root: Path) -> dict[str, str]:
    ignored = {".venv", "dist", "node_modules", "__pycache__"}
    return {
        path.relative_to(root).as_posix(): sha256(path)
        for path in root.rglob("*")
        if path.is_file() and not any(part in ignored for part in path.relative_to(root).parts)
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a generated-project upgrade matrix from a frozen source Golden set")
    parser.add_argument(
        "--source-goldens", "--p11-goldens", "--p10-goldens", "--p9-goldens",
        dest="source_goldens", type=Path, default=ROOT / "history/p11_golden_outputs"
    )
    parser.add_argument("--source-stage", default="P11")
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    args = parser.parse_args()
    work = args.work_dir.resolve()
    if work.exists() and any(work.iterdir()):
        raise SystemExit(f"Refusing to overwrite non-empty migration work directory: {work}")
    work.mkdir(parents=True, exist_ok=True)

    records = []
    for index, project_name in enumerate(CASES):
        case_dir = work / project_name
        case_dir.mkdir()
        zip_path = args.source_goldens / f"{project_name}.zip"
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(case_dir)
        root = case_dir / project_name
        user_file = None
        user_hash = None
        if index == 0:
            user_file = root / "src/json_batch_cli/__init__.py"
            user_file.write_text(user_file.read_text(encoding="utf-8") + "\n# real user evolution before Factory upgrade\n", encoding="utf-8")
            user_hash = sha256(user_file)
        before = snapshot(root)
        plan = plan_upgrade(root)
        if plan.status != "READY":
            raise SystemExit(f"{project_name}: DryRun not READY: {plan.blocked_reasons}")
        applied = apply_upgrade(root, confirm_plan_sha256=plan.plan_sha256)
        if user_file and sha256(user_file) != user_hash:
            raise SystemExit(f"{project_name}: user source changed during migration")
        overlay_ok, overlay_failures = verify_factory_overlay_manifest(root)
        if not overlay_ok:
            raise SystemExit(f"{project_name}: overlay manifest failed: {overlay_failures}")
        lock = json.loads((root / "project.lock.json").read_text(encoding="utf-8"))
        record = {
            "project": project_name,
            "dry_run_status": plan.status,
            "risk": plan.risk,
            "plan_sha256": plan.plan_sha256,
            "changed_paths": [c.path for c in plan.changes if c.action != "UNCHANGED"],
            "apply_status": applied["status"],
            "verification_status": applied["verification"]["status"],
            "lock_schema": lock["lock_schema_version"],
            "factory_version": lock["factory"]["version"],
            "extensions": lock.get("extensions", []),
            "overlay_manifest_verified": True,
            "user_source_preserved": bool(user_file is None or sha256(user_file) == user_hash),
            "rollback_bundle_sha256": applied["rollback_bundle_sha256"],
        }
        if index == 0:
            rolled = rollback_upgrade(root, Path(applied["rollback_bundle"]), confirm_bundle_sha256=applied["rollback_bundle_sha256"])
            record["rollback_status"] = rolled["status"]
            record["rollback_exact_preupgrade_state"] = snapshot(root) == before
            if not record["rollback_exact_preupgrade_state"]:
                raise SystemExit(f"{project_name}: rollback did not restore exact preupgrade file state")
        records.append(record)

    from project_factory.factory import FACTORY_STAGE
    evidence = {"status": "PASS", "source_stage": args.source_stage, "target_stage": FACTORY_STAGE, "cases": records}
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
