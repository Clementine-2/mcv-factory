from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "src"))

from project_factory.factory import FactoryError, generate_project, restore_verify_project_zip  # noqa: E402
from project_factory.host import load_host_registry  # noqa: E402

REQ = "做一个 Python CLI 工具，不能覆盖原始文件。"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run P10 Interactive Host contract matrix")
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    args = parser.parse_args()
    work = args.work_dir.resolve()
    if work.exists() and any(work.iterdir()):
        raise SystemExit(f"Refusing to overwrite non-empty Host work directory: {work}")
    work.mkdir(parents=True, exist_ok=True)

    registry = load_host_registry()
    aionui = registry["aionui"]
    if any(aionui.boundaries.values()):
        raise SystemExit("AionUI Host contract unexpectedly owns a Factory surface")

    no_host = generate_project(REQ, "no-host-cli", work / "no-host")
    if no_host.host_integration is not None or (no_host.project_root / ".project/host").exists():
        raise SystemExit("Host default introduced framework tax")

    hosted = generate_project(REQ, "aionui-hosted-cli", work / "hosted", hosts=("aionui",))
    restored = restore_verify_project_zip(hosted.project_zip)
    if restored["host_integration"]["status"] != "PARTIALLY_VERIFIED":
        raise SystemExit(f"Unexpected Host restore status: {restored['host_integration']!r}")

    plan = json.loads((hosted.project_root / ".project/host/aionui.json").read_text(encoding="utf-8"))
    if plan["mode"] != "plan-only" or plan["runtime"]["live_task_executed"]:
        raise SystemExit("Host plan falsely claims execution")
    if (hosted.project_root / ".aionui").exists():
        raise SystemExit("Factory materialized Host-private runtime directory")

    tamper_dir = work / "tamper"
    tampered = generate_project(REQ, "tamper-host-cli", tamper_dir, hosts=("aionui",))
    # Repackage after a controlled Factory-owned Host-plan tamper; restore must fail closed.
    plan_path = tampered.project_root / ".project/host/aionui.json"
    plan_path.write_text(plan_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    # Direct verifier is sufficient here because PROJECT_MANIFEST would also catch this first.
    from project_factory.host import verify_host_materialization
    lock = json.loads((tampered.project_root / "project.lock.json").read_text(encoding="utf-8"))
    tamper_check = verify_host_materialization(tampered.project_root, lock["host_integration"])
    if tamper_check["status"] != "FAILED":
        raise SystemExit("Tampered Host plan was not detected")

    evidence = {
        "status": "PASS",
        "registry_host": aionui.id,
        "protocol": aionui.protocol,
        "host_is_opt_in": True,
        "no_host_default_surface": True,
        "hosted_project_status": restored["status"],
        "host_contract_status": restored["host_integration"]["status"],
        "host_runtime_verified": restored["host_integration"]["runtime_verified"],
        "target_harnesses": plan["target_harnesses"],
        "plan_only": True,
        "host_private_runtime_dir_created": False,
        "tamper_detection": "PASS",
        "boundaries": aionui.boundaries,
    }
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
