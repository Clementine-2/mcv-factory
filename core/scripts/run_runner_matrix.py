from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from project_factory.decision import IntentSnapshot  # noqa: E402
from project_factory.factory import generate_project, restore_verify_project_zip  # noqa: E402
from project_factory.runner import RUNNER_ADMISSION_LOCK_PATH  # noqa: E402

CASES = (
    (
        "python-cli",
        "runner-python-cli",
        "做一个 Python CLI 工具，建立长期无人值守批次开发基础。",
        "codex",
    ),
    (
        "node-library",
        "runner-node-library",
        "做一个 JavaScript library，建立长期无人值守批次开发基础。",
        "claude",
    ),
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run current long-runtime plan-only Golden matrix")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists() and any(output.iterdir()):
        raise SystemExit(f"Refusing to overwrite non-empty Runner matrix directory: {output}")
    output.mkdir(parents=True, exist_ok=True)

    records = []
    for expected_profile, project_name, requirement, harness in CASES:
        result = generate_project(
            requirement,
            project_name,
            output,
            intent=IntentSnapshot(autonomy="long-running"),
            harnesses=(harness,),
            runner="dagu",
            runner_harness=harness,
        )
        restored = restore_verify_project_zip(result.project_zip)
        runner = restored["runner_integration"]
        lock = json.loads((result.project_root / "project.lock.json").read_text(encoding="utf-8"))
        if result.profile.profile_id != expected_profile:
            raise SystemExit(f"{project_name}: unexpected profile {result.profile.profile_id}")
        if runner["status"] != "PARTIALLY_VERIFIED" or runner["runtime_verified"]:
            raise SystemExit(f"{project_name}: Runner truth boundary changed: {runner!r}")
        if (result.project_root / RUNNER_ADMISSION_LOCK_PATH).exists():
            raise SystemExit(f"{project_name}: generation must not create runtime admission lock")
        if lock.get("runner_integration", {}).get("provider", {}).get("id") != "dagu":
            raise SystemExit(f"{project_name}: Project Lock missing Dagu runner receipt")
        records.append(
            {
                "project": project_name,
                "profile": expected_profile,
                "harness": harness,
                "runner": "dagu",
                "runner_status": runner["status"],
                "runner_runtime_verified": runner["runtime_verified"],
                "project_status": restored["status"],
                "manifest_verified": restored["manifest_verified"],
                "plan_sha256": lock["runner_integration"]["plan"]["sha256"],
                "admission_lock_created_during_generation": False,
                "limitation": "Dagu executable was not required for plan-only generation; live Dagu runtime remains unverified.",
            }
        )

    evidence = {
        "status": "PASS",
        "stage": "P12",
        "mode": "plan-only",
        "cases": records,
        "truth_boundary": "This matrix verifies Runner materialization and restore integrity, not live Dagu/Codex/Claude execution.",
    }
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
