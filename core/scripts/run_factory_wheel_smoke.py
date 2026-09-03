from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DECLARATIVE = ROOT / "fixtures/extensions/team-standard/extension.yaml"


def run(
    argv: list[str],
    *,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
    timeout_sec: int = 180,
) -> str:
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd or ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"Command timed out after {timeout_sec}s: {argv!r}\n{exc.stdout or ''}"
        ) from exc
    if completed.returncode != 0:
        raise RuntimeError(f"Command failed ({completed.returncode}): {argv!r}\n{completed.stdout}")
    return completed.stdout


def parse_json_output(text: str) -> dict:
    start = text.find("{")
    if start < 0:
        raise RuntimeError(f"Expected JSON output, got: {text}")
    return json.loads(text[start:])


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def make_checkpoint(path: Path) -> None:
    payload = b"wheel checkpoint smoke\n"
    digest = hashlib.sha256(payload).hexdigest()
    manifest = f"{digest}  payload.txt\n"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("checkpoint-root/payload.txt", payload)
        zf.writestr("checkpoint-root/MANIFEST.sha256", manifest)
        zf.writestr("checkpoint-root/CHECKPOINT_P12_COMPLETE.md", "wheel-smoke\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build current Project Factory wheel and smoke-test it outside the source tree")
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    version = str(project["version"])
    with tempfile.TemporaryDirectory(prefix="project-factory-wheel-") as td:
        root = Path(td)
        wheel_dir = root / "wheel"
        site = root / "site"
        state = root / "extensions.json"
        plan = root / "add-plan.json"
        out = root / "projects"
        wheel_dir.mkdir()
        site.mkdir()

        run([
            sys.executable, "-m", "pip", "wheel", "--no-build-isolation", "--no-deps",
            "--wheel-dir", str(wheel_dir), str(ROOT),
        ])
        wheels = sorted(wheel_dir.glob(f"project_factory_blueprint_kernel-{version}-*.whl"))
        if len(wheels) != 1:
            raise RuntimeError(f"Expected one Factory {version} wheel, got {wheels!r}")
        with zipfile.ZipFile(wheels[0]) as archive:
            names = set(archive.namelist())
            required = {
                "project_factory/extensions.py",
                "project_factory/host.py",
                "project_factory/runner.py",
                "project_factory/product.py",
                "project_factory/recovery.py",
                "project_factory/ux.py",
                "project_factory/registry_data/hosts.yaml",
                "project_factory/registry_data/runners.yaml",
                "project_factory/schema_data/extension-manifest.schema.json",
                "project_factory/schema_data/extension-set.schema.json",
                "project_factory/registry_data/profiles.yaml",
            }
            missing = sorted(required - names)
            if missing:
                raise RuntimeError(f"Factory wheel missing product package files: {missing}")
            entry_points = [name for name in names if name.endswith(".dist-info/entry_points.txt")]
            if len(entry_points) != 1 or "project-factory = project_factory.__main__:main" not in archive.read(entry_points[0]).decode("utf-8"):
                raise RuntimeError("Factory wheel is missing project-factory console entry point metadata")
            archive.extractall(site)

        env = dict(os.environ)
        env["PYTHONPATH"] = str(site)
        py = [sys.executable, "-m", "project_factory"]
        version_text = run(py + ["--version"], env=env).strip()
        help_text = run(py + ["--help"], env=env)
        if "status -> new -> check -> verify" not in help_text:
            raise RuntimeError("Wheel human help surface is missing the common-path UX")
        human_status = parse_json_output(run(py + ["status", "--json"], env=env))
        doctor = parse_json_output(run(py + ["doctor", "--deep"], env=env))
        if doctor["status"] == "BLOCKED" or doctor["deep_smoke"]["status"] != "PASS":
            raise RuntimeError(f"Wheel doctor failed: {doctor!r}")

        checkpoint = root / "checkpoint.zip"
        make_checkpoint(checkpoint)
        inspect = parse_json_output(run(py + ["checkpoint", "inspect", str(checkpoint)], env=env))
        restore_dir = root / "checkpoint-restore"
        restore_plan = parse_json_output(run(py + ["checkpoint", "plan", str(checkpoint), "--out-dir", str(restore_dir)], env=env))
        restored_checkpoint = parse_json_output(run(py + [
            "checkpoint", "restore", str(checkpoint), "--out-dir", str(restore_dir),
            "--confirm-plan-sha256", restore_plan["plan_sha256"],
        ], env=env))

        host_catalog = parse_json_output(run(py + ["host", "catalog"], env=env))
        if "aionui" not in host_catalog:
            raise RuntimeError(f"Factory wheel Host catalog missing aionui: {host_catalog!r}")
        inspected = parse_json_output(run(py + ["extension", "inspect", str(DECLARATIVE)], env=env))
        planned = parse_json_output(run(py + [
            "extension", "plan", "add", "--state", str(state), "--manifest", str(DECLARATIVE), "--out", str(plan)
        ], env=env))
        applied = parse_json_output(run(py + [
            "extension", "apply", "--state", str(state), "--plan", str(plan), "--confirm", planned["plan_sha256"]
        ], env=env))
        extension_doctor = parse_json_output(run(py + ["extension", "doctor", "--state", str(state)], env=env))
        generated = parse_json_output(run(py + [
            "generate", "--name", "wheel-runner-cli", "--output-dir", str(out), "--extension-set", str(state),
            "--autonomy", "long-running", "--harness", "codex", "--runner", "dagu", "--runner-harness", "codex",
            "做一个 Python CLI 工具。"
        ], env=env))
        verified = parse_json_output(run(py + [
            "restore-verify", generated["zip"], "--extension-set", str(state)
        ], env=env))
        project_root = Path(generated["project"])
        runner_inspect = parse_json_output(run(py + ["runner", "inspect", str(project_root)], env=env))
        if verified["status"] != "VERIFIED":
            raise RuntimeError(f"Factory wheel project verification failed: {verified!r}")
        if runner_inspect["status"] != "PARTIALLY_VERIFIED" or runner_inspect["runtime"]["status"] != "UNAVAILABLE":
            raise RuntimeError(f"Runner wheel truth boundary changed: {runner_inspect!r}")

        ux_out = root / "ux-projects"
        ux_new = parse_json_output(run(py + [
            "new", "wheel-human-cli", "做一个 Python 命令行工具。", "--out", str(ux_out), "--json"
        ], env=env))
        ux_check = parse_json_output(run(py + ["check", ux_new["project"], "--json"], env=env))
        ux_verify = parse_json_output(run(py + ["verify", ux_new["zip"], "--json"], env=env))
        if ux_check["status"] != "PASS" or ux_verify["status"] != "VERIFIED":
            raise RuntimeError(f"Human UX wheel flow failed: check={ux_check!r}, verify={ux_verify!r}")

        venv = root / "venv"
        isolated_env = dict(os.environ)
        isolated_env.pop("PYTHONPATH", None)
        isolated_env.pop("PYTHONHOME", None)
        run([sys.executable, "-m", "venv", str(venv)], env=isolated_env)
        venv_bin = venv / ("Scripts" if os.name == "nt" else "bin")
        venv_python = venv_bin / ("python.exe" if os.name == "nt" else "python")
        console = venv_bin / ("project-factory.exe" if os.name == "nt" else "project-factory")
        install_output = run(
            [str(venv_python), "-m", "pip", "install", "--no-deps", str(wheels[0])],
            cwd=root,
            env=isolated_env,
        )
        if not console.is_file():
            raise RuntimeError(
                "Wheel install returned success but console script was not materialized. "
                f"PYTHONPATH was scrubbed; install output follows:\n{install_output}"
            )
        dependency_site = next((Path(item) for item in sys.path if item and (Path(item) / "yaml").is_dir() and (Path(item) / "jsonschema").is_dir()), None)
        if dependency_site is None:
            raise RuntimeError("Unable to locate the already-installed pinned dependency site for offline console smoke")
        console_env = dict(os.environ)
        console_env["PYTHONPATH"] = str(dependency_site)
        console_version = run([str(console), "--version"], cwd=root, env=console_env).strip()
        console_help = run([str(console), "--help"], cwd=root, env=console_env)
        console_doctor = parse_json_output(run([str(console), "doctor"], cwd=root, env=console_env))
        if console_doctor["status"] == "BLOCKED":
            raise RuntimeError(f"Installed console-script doctor blocked: {console_doctor!r}")

        evidence = {
            "status": "PASS",
            "wheel": wheels[0].name,
            "wheel_sha256": sha256(wheels[0]),
            "outside_source_tree": True,
            "required_product_package_files": "PASS",
            "console_entry_point_metadata": "PASS",
            "module_version": version_text,
            "human_help_surface": "PASS",
            "human_status": human_status["status"],
            "human_new": ux_new["status"],
            "human_check": ux_check["status"],
            "human_verify": ux_verify["status"],
            "doctor_status": doctor["status"],
            "doctor_deep_smoke": doctor["deep_smoke"]["status"],
            "checkpoint_inspect": inspect["status"],
            "checkpoint_restore": restored_checkpoint["status"],
            "host_catalog_aionui": "PASS",
            "extension_inspect": inspected["status"],
            "extension_plan": planned["status"],
            "extension_apply": applied["status"],
            "extension_doctor": extension_doctor["status"],
            "generated_profile": generated["profile"],
            "project_status": verified["status"],
            "runner_status": runner_inspect["status"],
            "runner_runtime_status": runner_inspect["runtime"]["status"],
            "runner_runtime_verified": runner_inspect["runtime"]["runtime_verified"],
            "console_script_installed_in_temp_venv": True,
            "venv_install_pythonpath_scrubbed": True,
            "console_version": console_version,
            "console_human_help_surface": "PASS" if "status -> new -> check -> verify" in console_help else "FAILED",
            "console_doctor_status": console_doctor["status"],
            "dependency_resolution_tested": False,
            "dependency_runtime_source": "preinstalled-host-site-packages injected into isolated console smoke",
            "standalone_offline_install_verified": False,
            "global_environment_modified": False,
        }
        if args.evidence:
            args.evidence.parent.mkdir(parents=True, exist_ok=True)
            args.evidence.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(evidence, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
