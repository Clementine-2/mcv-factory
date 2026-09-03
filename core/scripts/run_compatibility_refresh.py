from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from project_factory.compatibility import build_status_report  # noqa: E402
from project_factory.harness import load_harness_registry  # noqa: E402
from project_factory.host import load_host_registry  # noqa: E402
from project_factory.process import load_process_registry  # noqa: E402
from project_factory.runner import load_runner_registry, probe_runner_runtime  # noqa: E402


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def registry_hashes() -> dict[str, str]:
    root = ROOT / "src/project_factory/registry_data"
    return {path.name: sha256(path) for path in sorted(root.glob("*.yaml"))}


def version(executable: str, args: list[str], pattern: str = r"(\d+\.\d+\.\d+)") -> str | None:
    resolved = shutil.which(executable)
    if not resolved:
        return None
    try:
        result = subprocess.run(
            [resolved, *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return None
    match = re.search(pattern, result.stdout)
    return match.group(1) if result.returncode == 0 and match else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Bounded compatibility refresh from explicit observation + local probes")
    parser.add_argument("--observation", type=Path, default=ROOT / "compatibility/observations/2026-08-30.yaml")
    parser.add_argument("--evidence", required=True, type=Path)
    args = parser.parse_args()
    before = registry_hashes()
    local = {
        "uv": version("uv", ["--version"]),
        "npm": version("npm", ["--version"]),
        "node": version("node", ["--version"]),
    }
    report = build_status_report(
        ROOT / "src/project_factory/registry_data/compatibility.yaml",
        args.observation,
        runtime_versions={"node": local["node"]} if local["node"] else {},
        local_versions={"uv": local["uv"], "npm": local["npm"]},
    )
    runners = {runner_id: probe_runner_runtime(spec) for runner_id, spec in load_runner_registry().items()}
    harnesses = {
        key: {"status": "AVAILABLE_UNVERIFIED" if shutil.which(spec.executable) else "UNAVAILABLE", "runtime_verified": False}
        for key, spec in load_harness_registry().items()
    }
    processes = {
        key: {"status": "AVAILABLE_UNVERIFIED" if shutil.which(spec.executable) else "UNAVAILABLE", "runtime_verified": False}
        for key, spec in load_process_registry().items()
    }
    hosts = {
        key: {"status": "CONTRACT_ONLY", "protocol": spec.protocol, "runtime_verified": False}
        for key, spec in load_host_registry().items()
    }
    after = registry_hashes()
    if before != after:
        raise RuntimeError("Compatibility refresh mutated stable Registry data")
    evidence = {
        "status": "PASS",
        "mode": "observation-plus-local-probe",
        "network_access_by_script": False,
        "automatic_promotion": False,
        "registry_mutated": False,
        "observation": str(args.observation),
        "local_versions": local,
        "compatibility": report,
        "runners": runners,
        "harnesses": harnesses,
        "process_integrations": processes,
        "hosts": hosts,
        "registry_sha256": after,
    }
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
