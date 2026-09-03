from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
SRC = ROOT / "fixtures" / "extensions" / "trusted-wheel-src"
MANIFEST_SOURCE = ROOT / "fixtures" / "extensions" / "trusted-lab"


def run(argv: list[str], *, cwd: Path | None = None) -> None:
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
        raise RuntimeError(f"Command timed out after 180s: {argv!r}\n{exc.stdout or ''}") from exc
    if completed.returncode != 0:
        raise RuntimeError(f"Command failed ({completed.returncode}): {argv!r}\n{completed.stdout}")


def prepare_extension(ext: Path, wheel: Path) -> tuple[Path, Path]:
    ext.mkdir()
    target = ext / "plugin_site"
    target.mkdir()
    shutil.copy2(MANIFEST_SOURCE / "extension.yaml", ext / "extension.yaml")
    shutil.copytree(MANIFEST_SOURCE / "assets", ext / "assets")
    run([
        sys.executable,
        "-m",
        "pip",
        "install",
        "--no-deps",
        "--no-index",
        "--target",
        str(target),
        str(wheel),
    ])
    return ext / "extension.yaml", target


def main() -> int:
    from project_factory.extensions import apply_extension_plan, load_extension_runtime, plan_add_extension
    from project_factory.factory import generate_project, restore_verify_project_zip

    with tempfile.TemporaryDirectory(prefix="project-factory-p9-wheel-") as td:
        root = Path(td)
        wheel_a_dir = root / "wheel-a"
        wheel_b_dir = root / "wheel-b"
        out = root / "out"
        wheel_a_dir.mkdir()
        wheel_b_dir.mkdir()

        run([
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-build-isolation",
            "--no-deps",
            "--wheel-dir",
            str(wheel_a_dir),
            str(SRC),
        ])
        wheels = sorted(wheel_a_dir.glob("project_factory_trusted_lab-2.0.0-*.whl"))
        if len(wheels) != 1:
            raise RuntimeError(f"Expected exactly one trusted extension wheel, got {wheels!r}")
        wheel_a = wheels[0]
        wheel_b = wheel_b_dir / wheel_a.name
        shutil.copy2(wheel_a, wheel_b)

        manifest_a, _ = prepare_extension(root / "ext-a", wheel_a)
        manifest_b, _ = prepare_extension(root / "ext-b", wheel_b)

        receipts = []
        states = []
        for index, manifest_path in enumerate((manifest_a, manifest_b), start=1):
            state = root / f"extensions-{index}.json"
            plan = plan_add_extension(state, manifest_path, trust_code=True)
            apply_extension_plan(state, plan, confirm_plan_sha256=plan.plan_sha256)
            runtime = load_extension_runtime(state)
            receipt = runtime.receipt()["extensions"][0]
            if not receipt.get("distribution_sha256") or receipt.get("distribution_file_count", 0) <= 0:
                raise RuntimeError("Trusted wheel distribution fingerprint was not recorded")
            receipts.append(receipt)
            states.append(state)

        if receipts[0]["distribution_sha256"] != receipts[1]["distribution_sha256"]:
            raise RuntimeError("Stable distribution fingerprint changed across equivalent installs from different wheel paths")

        result = generate_project("做一个 Python CLI 工具。", "wheel-trusted-cli", out, extension_set=states[0])
        verify = restore_verify_project_zip(result.project_zip, extension_set=states[0])
        if verify["status"] != "VERIFIED":
            raise RuntimeError(f"Trusted wheel generated project did not verify: {verify!r}")
        lock = json.loads((result.project_root / "project.lock.json").read_text(encoding="utf-8"))
        locked = lock["extensions"][0]
        if locked["distribution_sha256"] != receipts[0]["distribution_sha256"]:
            raise RuntimeError("Project Lock distribution fingerprint differs from runtime receipt")

        print(json.dumps({
            "status": "PASS",
            "wheel": wheel_a.name,
            "extension_id": locked["id"],
            "extension_version": locked["version"],
            "distribution": locked["distribution"],
            "distribution_version": locked["distribution_version"],
            "distribution_sha256": locked["distribution_sha256"],
            "distribution_file_count": locked["distribution_file_count"],
            "equivalent_install_fingerprint_stable": True,
            "project_status": verify["status"],
            "global_install_modified": False,
        }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
