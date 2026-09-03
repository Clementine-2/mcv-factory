from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from project_factory.factory import generate_project  # noqa: E402
from project_factory.ownership import verify_factory_overlay_manifest  # noqa: E402
from project_factory.upgrade import plan_upgrade  # noqa: E402


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run(argv: list[str], cwd: Path) -> dict:
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=180,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            json.dumps(
                {
                    "argv": argv,
                    "returncode": 124,
                    "timeout_sec": 180,
                    "output": str(exc.stdout or "")[-12000:],
                },
                ensure_ascii=False,
            )
        ) from exc
    result = {"argv": argv, "returncode": completed.returncode, "output": completed.stdout[-12000:]}
    if completed.returncode != 0:
        raise RuntimeError(json.dumps(result, ensure_ascii=False))
    return result


PYTHON_IMPL = r'''from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

__version__ = "0.1.0"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_manifest(text: str) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        digest, relative = line.split("  ", 1)
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"unsafe manifest path: {relative}")
        entries.append((digest.casefold(), relative))
    return entries


def verify_manifest(root: Path, manifest: Path) -> dict:
    failures: list[dict[str, str]] = []
    entries = parse_manifest(manifest.read_text(encoding="utf-8"))
    for expected, relative in entries:
        path = root / relative
        if not path.is_file():
            failures.append({"path": relative, "reason": "missing"})
            continue
        actual = _sha256(path)
        if actual != expected:
            failures.append({"path": relative, "reason": "sha256", "actual": actual})
    return {"status": "PASS" if not failures else "FAILED", "entries": len(entries), "failures": failures}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="checkpoint-auditor")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)
    report = verify_manifest(args.root, args.manifest)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 2
'''

PYTHON_TESTS = r'''from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from checkpoint_auditor import parse_manifest, verify_manifest


class CheckpointAuditorTests(unittest.TestCase):
    def test_valid_manifest_passes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            data = b"hello\n"
            (root / "a.txt").write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            manifest = root / "manifest.sha256"
            manifest.write_text(f"{digest}  a.txt\n")
            self.assertEqual(verify_manifest(root, manifest)["status"], "PASS")

    def test_changed_file_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a.txt").write_text("changed\n")
            manifest = root / "manifest.sha256"
            manifest.write_text(f"{'0'*64}  a.txt\n")
            report = verify_manifest(root, manifest)
            self.assertEqual(report["status"], "FAILED")
            self.assertEqual(report["failures"][0]["reason"], "sha256")

    def test_missing_file_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest = root / "manifest.sha256"
            manifest.write_text(f"{'0'*64}  missing.txt\n")
            self.assertEqual(verify_manifest(root, manifest)["failures"][0]["reason"], "missing")

    def test_unsafe_path_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_manifest(f"{'0'*64}  ../escape.txt\n")


if __name__ == "__main__":
    unittest.main()
'''

NODE_INDEX = r'''export { summarizeEvidence, overallStatus } from "./summary.js";
export { normalizeRecord } from "./validate.js";
'''

NODE_VALIDATE = r'''const ALLOWED = new Set(["VERIFIED", "PARTIALLY_VERIFIED", "UNVERIFIED", "FAILED"]);

export function normalizeRecord(record) {
  if (!record || typeof record !== "object") throw new TypeError("record must be an object");
  const id = String(record.id ?? "").trim();
  const status = String(record.status ?? "").trim();
  if (!id) throw new TypeError("record id is required");
  if (!ALLOWED.has(status)) throw new TypeError(`unsupported status: ${status}`);
  return { id, status, material: record.material !== false };
}
'''

NODE_SUMMARY = r'''import { normalizeRecord } from "./validate.js";

export function overallStatus(records) {
  const normalized = records.map(normalizeRecord).filter((item) => item.material);
  if (normalized.length === 0) return "UNVERIFIED";
  const statuses = new Set(normalized.map((item) => item.status));
  if (statuses.has("FAILED")) return "FAILED";
  if (statuses.size === 1 && statuses.has("VERIFIED")) return "VERIFIED";
  if (statuses.size === 1 && statuses.has("UNVERIFIED")) return "UNVERIFIED";
  return "PARTIALLY_VERIFIED";
}

export function summarizeEvidence(records) {
  const normalized = records.map(normalizeRecord);
  const counts = { VERIFIED: 0, PARTIALLY_VERIFIED: 0, UNVERIFIED: 0, FAILED: 0 };
  for (const item of normalized) counts[item.status] += 1;
  return {
    status: overallStatus(normalized),
    total: normalized.length,
    material: normalized.filter((item) => item.material).length,
    counts,
  };
}
'''

NODE_TESTS = r'''import test from "node:test";
import assert from "node:assert/strict";
import { normalizeRecord, overallStatus, summarizeEvidence } from "../src/index.js";

test("all verified stays verified", () => {
  assert.equal(overallStatus([{id:"a", status:"VERIFIED"}, {id:"b", status:"VERIFIED"}]), "VERIFIED");
});

test("failure dominates", () => {
  assert.equal(overallStatus([{id:"a", status:"VERIFIED"}, {id:"b", status:"FAILED"}]), "FAILED");
});

test("mixed verified and unverified is partial", () => {
  assert.equal(overallStatus([{id:"a", status:"VERIFIED"}, {id:"b", status:"UNVERIFIED"}]), "PARTIALLY_VERIFIED");
});

test("all unverified stays unverified", () => {
  assert.equal(overallStatus([{id:"a", status:"UNVERIFIED"}]), "UNVERIFIED");
});

test("non-material record does not reduce material overall", () => {
  assert.equal(overallStatus([{id:"a", status:"VERIFIED"}, {id:"note", status:"UNVERIFIED", material:false}]), "VERIFIED");
});

test("summary counts every claim", () => {
  const result = summarizeEvidence([{id:"a", status:"VERIFIED"}, {id:"b", status:"UNVERIFIED"}]);
  assert.equal(result.total, 2);
  assert.equal(result.counts.VERIFIED, 1);
  assert.equal(result.counts.UNVERIFIED, 1);
});

test("invalid status is rejected", () => {
  assert.throws(() => normalizeRecord({id:"a", status:"DONE"}), /unsupported status/);
});
'''


def python_dogfood(work: Path) -> dict:
    generated = generate_project(
        "做一个 Python 命令行工具，验证 SHA256 manifest 并输出机器可读报告。不能覆盖被检查文件。",
        "checkpoint-auditor",
        work,
    )
    root = generated.project_root
    source = root / "src/checkpoint_auditor/__init__.py"
    source.write_text(PYTHON_IMPL, encoding="utf-8")
    tests = root / "tests/test_smoke.py"
    tests.write_text(PYTHON_TESTS, encoding="utf-8")
    source_hash = sha256(source)
    commands = [
        run(["uv", "--offline", "run", "python", "-m", "unittest", "discover", "-s", "tests", "-v"], root),
        run(["uv", "--offline", "build"], root),
    ]
    overlay_ok, overlay_failures = verify_factory_overlay_manifest(root)
    plan = plan_upgrade(root)
    changed = [item.path for item in plan.changes if item.action != "UNCHANGED"]
    if any(path.startswith("src/") or path.startswith("tests/") for path in changed):
        raise RuntimeError(f"Factory upgrade targeted dogfood business files: {changed}")
    if sha256(source) != source_hash:
        raise RuntimeError("Python dogfood source changed during Factory analysis")
    return {
        "status": "PASS",
        "project": "checkpoint-auditor",
        "family": "python-cli",
        "business_scope": "small",
        "native_tests": commands[0]["returncode"],
        "native_build": commands[1]["returncode"],
        "factory_overlay_verified": overlay_ok,
        "overlay_failures": overlay_failures,
        "upgrade_plan_status": plan.status,
        "upgrade_targeted_business_files": False,
        "business_source_sha256": source_hash,
        "factory_generated_zip_status": generated.verification["status"],
    }


def node_dogfood(work: Path) -> dict:
    generated = generate_project(
        "做一个 JavaScript library，汇总 Evidence claim 状态并保持 VERIFIED/PARTIALLY_VERIFIED/UNVERIFIED/FAILED 语义。",
        "evidence-rollup-js",
        work,
    )
    root = generated.project_root
    (root / "src/index.js").write_text(NODE_INDEX, encoding="utf-8")
    (root / "src/validate.js").write_text(NODE_VALIDATE, encoding="utf-8")
    (root / "src/summary.js").write_text(NODE_SUMMARY, encoding="utf-8")
    (root / "tests/smoke.test.js").write_text(NODE_TESTS, encoding="utf-8")
    source_hashes = {path.name: sha256(path) for path in (root / "src").glob("*.js")}
    commands = [
        run(["npm", "test"], root),
        run(["npm", "pack", "--ignore-scripts"], root),
    ]
    overlay_ok, overlay_failures = verify_factory_overlay_manifest(root)
    plan = plan_upgrade(root)
    changed = [item.path for item in plan.changes if item.action != "UNCHANGED"]
    if any(path.startswith("src/") or path.startswith("tests/") for path in changed):
        raise RuntimeError(f"Factory upgrade targeted dogfood business files: {changed}")
    for path in (root / "src").glob("*.js"):
        if sha256(path) != source_hashes[path.name]:
            raise RuntimeError("Node dogfood source changed during Factory analysis")
    return {
        "status": "PASS",
        "project": "evidence-rollup-js",
        "family": "node-library",
        "business_scope": "medium",
        "native_tests": commands[0]["returncode"],
        "native_pack": commands[1]["returncode"],
        "factory_overlay_verified": overlay_ok,
        "overlay_failures": overlay_failures,
        "upgrade_plan_status": plan.status,
        "upgrade_targeted_business_files": False,
        "business_source_sha256": source_hashes,
        "factory_generated_zip_status": generated.verification["status"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="P12 small/medium real-project dogfood")
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    args = parser.parse_args()
    work = args.work_dir.resolve()
    if work.exists() and any(work.iterdir()):
        raise SystemExit(f"Refusing to overwrite non-empty dogfood directory: {work}")
    work.mkdir(parents=True, exist_ok=True)
    report = {
        "status": "PASS",
        "cases": [python_dogfood(work / "python"), node_dogfood(work / "node")],
        "limitations": [
            "Dogfood uses real native tests/builds but does not publish packages to public registries.",
            "Live Dagu/Codex/Claude long-running dogfood is a separate external-runtime gate.",
        ],
    }
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
