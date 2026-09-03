from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from project_factory.factory import generate_project, restore_verify_project_zip  # noqa: E402


CASES = (
    (
        "python-cli",
        "json-batch-cli",
        "做一个 Python 命令行工具，批量读取一个目录里的 JSON 并转换格式。不能覆盖原始文件。",
    ),
    (
        "python-library",
        "text-normalizer-lib",
        "做一个 Python library，提供可复用的文本标准化能力，长期维护。",
    ),
    (
        "node-library",
        "string-tools-js",
        "做一个 JavaScript library，提供可复用的字符串处理能力，长期维护。",
    ),
    (
        "browser-extension-js",
        "cross-browser-helper",
        "做一个 JavaScript 浏览器扩展，必须支持 Chrome 和 Firefox，先建立可靠项目基地。",
    ),
    (
        "python-mcp-server",
        "echo-mcp-server",
        "做一个 Python MCP 服务器，向外部 Agent 暴露工具、资源和提示词。",
    ),
    (
        "browser-extension-wxt",
        "cross-browser-wxt",
        "做一个 TypeScript 浏览器扩展，必须支持 Chrome 和 Firefox，先建立可靠项目基地。",
    ),
    (
        "python-http-service",
        "health-api",
        "做一个 Python 后端服务，提供 HTTP API。",
    ),
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the current Golden Project harness/process verification matrix")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists() and any(output.iterdir()):
        raise SystemExit(f"Refusing to overwrite non-empty Golden output directory: {output}")
    output.mkdir(parents=True, exist_ok=True)

    records = []
    for expected_profile, project_name, requirement in CASES:
        result = generate_project(requirement, project_name, output, process_integration="spec-kit", process_mode="plan", hosts=("aionui",))
        restored = restore_verify_project_zip(result.project_zip)
        if result.profile.profile_id != expected_profile or restored["profile"] != expected_profile:
            raise SystemExit(f"Profile mismatch for {project_name}")
        runner_dir_present = (result.project_root / ".project/runner").exists()
        if result.runner_integration is not None or runner_dir_present or restored["runner_integration"]["status"] != "NOT_CONFIGURED":
            raise SystemExit(f"Unexpected Runner framework tax for default project {project_name}")
        records.append(
            {
                "project": project_name,
                "profile": expected_profile,
                "provider": result.provider.provider_id,
                "zip": result.project_zip.name,
                "zip_sha256": restored["zip_sha256"],
                "manifest_verified": restored["manifest_verified"],
                "verification_gate_count": len(restored["verification"]["gates"]),
                "claim_summary": restored["verification"]["claim_summary"],
                "generation_limitations": result.verification.get("limitations", []),
                "harness_status": restored["harness_compatibility"]["status"],
                "harnesses": sorted(restored["harness_compatibility"]["adapters"]),
                "process_status": restored["process_integration"]["status"],
                "process_runtime_verified": restored["process_integration"]["runtime_verified"],
                "host_status": restored["host_integration"]["status"],
                "hosts": restored["host_integration"]["hosts"],
                "host_runtime_verified": restored["host_integration"]["runtime_verified"],
                "runner_status": restored["runner_integration"]["status"],
                "runner_runtime_verified": restored["runner_integration"]["runtime_verified"],
                "runner_surface_present": runner_dir_present,
                "status": restored["status"],
            }
        )
    evidence = {
        "status": "VERIFIED" if all(case["manifest_verified"] for case in records) else "FAILED",
        "note": "Matrix status means project required gates/manifests passed. Harness/Host runtime remains evidence-scoped, Spec Kit stays plan-only, and default projects must remain Runner-free unless real long-running intent is selected.",
        "cases": records,
    }
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
