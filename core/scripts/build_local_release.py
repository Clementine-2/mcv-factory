from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a local-install Project Factory release bundle")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists() and any(output.iterdir()):
        raise SystemExit(f"Refusing to overwrite non-empty release output directory: {output}")
    output.mkdir(parents=True, exist_ok=True)
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    version = str(project["version"])

    with tempfile.TemporaryDirectory(prefix="project-factory-release-") as td:
        stage = Path(td) / f"project-factory-{version}-local"
        stage.mkdir(parents=True)
        wheel_dir = stage / "wheel"
        wheel_dir.mkdir()
        try:
            result = subprocess.run([
                sys.executable, "-m", "pip", "wheel", "--no-build-isolation", "--no-deps",
                "--wheel-dir", str(wheel_dir), str(ROOT),
            ], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False, timeout=180)
        except subprocess.TimeoutExpired as exc:
            raise SystemExit(f"Wheel build timed out after 180s.\n{exc.stdout or ''}") from exc
        if result.returncode != 0:
            raise SystemExit(result.stdout)
        wheels = sorted(wheel_dir.glob(f"project_factory_blueprint_kernel-{version}-*.whl"))
        if len(wheels) != 1:
            raise SystemExit(f"Expected one wheel, got: {wheels}")
        (stage / "requirements.txt").write_text((ROOT / "requirements.txt").read_text(encoding="utf-8"), encoding="utf-8")
        install = f'''# Project Factory {version} — Local Install\n\nThis bundle contains the Project Factory wheel and exact Python dependency pins. It does **not** contain third-party dependency wheels, so it is not an offline dependency mirror.\n\n## Recommended install\n\nCreate a dedicated virtual environment and install the wheel:\n\n```bash\npython -m venv .venv\n.venv/bin/python -m pip install wheel/{wheels[0].name}\n.venv/bin/project-factory doctor --deep\n```\n\nWindows uses `.venv\\Scripts\\python.exe` and `.venv\\Scripts\\project-factory.exe`.\n\nIf the machine cannot reach the configured Python package index and does not already have the pinned dependencies available, dependency installation will fail. Do not describe this bundle as fully offline/self-contained.\n\n## First project\n\n```bash\n.venv/bin/project-factory status\n.venv/bin/project-factory new my-project "做一个 Python 命令行工具。"\n.venv/bin/project-factory check ./out/my-project\n.venv/bin/project-factory verify ./out/my-project.zip\n```\n\n## Recovery\n\nUse `project-factory checkpoint inspect`, then `checkpoint plan`, then `checkpoint restore --confirm-plan-sha256 ...`. Restore never overwrites an existing destination.\n'''
        (stage / "INSTALL.md").write_text(install, encoding="utf-8")
        checksums = []
        for path in sorted(stage.rglob("*")):
            if path.is_file() and path.name != "CHECKSUMS.sha256":
                checksums.append(f"{sha256(path)}  {path.relative_to(stage).as_posix()}")
        (stage / "CHECKSUMS.sha256").write_text("\n".join(checksums) + "\n", encoding="utf-8")
        bundle = output / f"project-factory-{version}-local.zip"
        with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(stage.rglob("*")):
                if path.is_file():
                    zf.write(path, f"{stage.name}/{path.relative_to(stage).as_posix()}")
        with zipfile.ZipFile(bundle) as zf:
            bad = zf.testzip()
            if bad:
                raise SystemExit(f"Release bundle CRC failure: {bad}")
        evidence = {
            "status": "PASS",
            "version": version,
            "bundle": str(bundle),
            "bundle_sha256": sha256(bundle),
            "wheel": wheels[0].name,
            "wheel_sha256": sha256(wheels[0]),
            "third_party_dependency_wheels_included": False,
            "fully_offline_self_contained": False,
            "zip_crc": "PASS",
        }
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(evidence, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
