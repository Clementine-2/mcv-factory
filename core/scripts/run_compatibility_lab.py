from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "src"))

from project_factory.compatibility import (  # noqa: E402
    build_status_report,
    load_compatibility_registry,
    run_local_provider_lab,
)


def probe(executable: str, args: tuple[str, ...], regex: str) -> str | None:
    resolved = shutil.which(executable)
    if not resolved:
        return None
    result = subprocess.run([resolved, *args], text=True, capture_output=True, check=False, timeout=30)
    text = (result.stdout or "") + "\n" + (result.stderr or "")
    match = re.search(regex, text)
    return match.group(1) if result.returncode == 0 and match else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--observation", type=Path, default=ROOT / "compatibility/observations/2026-08-30.yaml")
    parser.add_argument("--output", type=Path, default=ROOT / "evidence/p7/P7_COMPATIBILITY_LAB_REPORT.json")
    args = parser.parse_args()

    versions = {
        "uv": probe("uv", ("--version",), r"(\d+\.\d+\.\d+)"),
        "npm": probe("npm", ("--version",), r"(\d+\.\d+\.\d+)"),
        "node": probe("node", ("--version",), r"v?(\d+\.\d+\.\d+)"),
        "spec-kit": probe("specify", ("version",), r"(\d+\.\d+\.\d+)"),
        "codex": probe("codex", ("--version",), r"(\d+\.\d+\.\d+)"),
        "claude": probe("claude", ("--version",), r"(\d+\.\d+\.\d+)"),
    }
    subjects = load_compatibility_registry()
    status = build_status_report(
        ROOT / "src/project_factory/registry_data/compatibility.yaml",
        args.observation,
        runtime_versions={"node": versions["node"]} if versions["node"] else {},
        local_versions={key: versions.get(key) for key in ("uv", "npm", "spec-kit", "codex", "claude")},
    )
    local_labs = {}
    for subject_id, executable, version_args, regex in (
        ("uv", "uv", ("--version",), r"(\d+\.\d+\.\d+)"),
        ("npm", "npm", ("--version",), r"(\d+\.\d+\.\d+)"),
    ):
        local_labs[subject_id] = run_local_provider_lab(
            subjects[subject_id], executable=executable, version_args=version_args, version_regex=regex
        )

    report = {
        "schema_version": "0.1",
        "observation_file": args.observation.relative_to(ROOT).as_posix(),
        "environment": versions,
        "status_report": status,
        "local_supported_revalidation": local_labs,
        "promotion_proposals": [],
        "automatic_registry_mutation": False,
        "notes": [
            "Dynamic upstream observations are evidence inputs, not persistent support state.",
            "A candidate cannot become SUPPORTED without its required local lab checks.",
            "This run had no new candidate artifact available for isolated execution, so no new version was promoted.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "environment": versions,
        "local_states": {key: value["state"] for key, value in local_labs.items()},
        "candidate_states": [
            {"subject": item["subject"], "version": item["version"], "state": item["state"], "reason": item["reason"]}
            for item in status["candidates"]
        ],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
