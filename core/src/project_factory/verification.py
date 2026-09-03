from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .recipes import portable_command_result


class VerificationError(RuntimeError):
    """Raised when a trusted verification suite is invalid or cannot be evaluated."""


class ProviderView(Protocol):
    provider_id: str
    provider_version: str
    executable: str


@dataclass(frozen=True)
class GateSpec:
    id: str
    target: str
    method: str
    command: tuple[str, ...] = ()
    expected_stdout_contains: tuple[str, ...] = ()
    artifact_patterns: tuple[str, ...] = ()
    min_artifacts: int = 0
    required: bool = True
    timeout_sec: int = 300


@dataclass(frozen=True)
class ClaimSpec:
    id: str
    statement: str
    scope: str
    gate_ids: tuple[str, ...] = ()
    material: bool = True
    limitation: str | None = None


@dataclass(frozen=True)
class VerificationSuite:
    id: str
    version: str
    scope: str
    gates: tuple[GateSpec, ...]
    claims: tuple[ClaimSpec, ...]
    runtime_kind: str
    limitations: tuple[str, ...] = ()


def _python_package_name(project_name: str) -> str:
    return project_name.casefold().replace("-", "_").replace(".", "_")


def _command_gate(
    gate_id: str,
    target: str,
    command: list[str],
    *stdout_contains: str,
    required: bool = True,
    timeout_sec: int = 300,
) -> GateSpec:
    return GateSpec(
        id=gate_id,
        target=target,
        method="command",
        command=tuple(command),
        expected_stdout_contains=tuple(stdout_contains),
        required=required,
        timeout_sec=timeout_sec,
    )


def build_verification_suite(
    suite_id: str,
    project_name: str,
    provider: ProviderView,
    *,
    extension_runtime: Any | None = None,
) -> VerificationSuite:
    """Return a trusted suite definition. Registry data may select an id, but cannot inject commands."""
    package_name = _python_package_name(project_name)
    executable = provider.executable

    from .verification_suites import first_party_suites

    first_party = first_party_suites().get(suite_id)
    if first_party is not None:
        suite = first_party(project_name, provider)
        if not isinstance(suite, VerificationSuite):
            raise VerificationError(f"First-party verification builder {suite_id!r} returned an invalid suite.")
        _validate_suite(suite)
        return suite

    if suite_id == "python-cli":
        gates = (
            _command_gate("cli-runs", "generated CLI entry point", [executable, "--offline", "run", project_name], "Project scaffold ready"),
            _command_gate("cli-version", "generated CLI version", [executable, "--offline", "run", project_name, "--version"], "0.1.0"),
            _command_gate("unit-tests", "local unit tests", [executable, "--offline", "run", "python", "-m", "unittest", "discover", "-s", "tests", "-v"]),
            _command_gate("pytest-tests", "local pytest", [executable, "--offline", "run", "pytest", "-q"], "passed", required=False),
            _command_gate("package-build", "local Python package build", [executable, "--offline", "build"]),
            GateSpec("package-artifacts", "wheel and source distribution artifacts", "artifact", artifact_patterns=("dist/*.whl", "dist/*.tar.gz"), min_artifacts=2),
        )
        claims = (
            ClaimSpec("entry-point-usable", "The generated CLI entry point runs locally.", "local generated scaffold", ("cli-runs", "cli-version")),
            ClaimSpec("tests-pass", "The generated scaffold unit tests pass locally.", "local generated scaffold", ("unit-tests",)),
            ClaimSpec(
                "pytest-pass",
                "The generated scaffold also passes under pinned pytest.",
                "local generated scaffold",
                ("pytest-tests",),
                False,
            ),
            ClaimSpec("package-builds", "The generated scaffold builds a wheel and source distribution locally.", "local package build", ("package-build", "package-artifacts")),
        )
        return VerificationSuite("python-cli", "0.1", "generated Python CLI bootstrap scaffold", gates, claims, "python", (
            "Public PyPI publication and installation are outside this verification scope.",
            "pytest is additive; unittest remains the required local test gate. Overlay upgrades do not rewrite pyproject.toml to inject pytest.",
        ))

    if suite_id == "python-library":
        gates = (
            _command_gate("library-imports", "generated Python library import", [executable, "--offline", "run", "python", "-c", f"import {package_name}; print({package_name}.scaffold_status())"], "scaffold ready"),
            _command_gate("unit-tests", "local unit tests", [executable, "--offline", "run", "python", "-m", "unittest", "discover", "-s", "tests", "-v"]),
            _command_gate("pytest-tests", "local pytest", [executable, "--offline", "run", "pytest", "-q"], "passed", required=False),
            _command_gate("package-build", "local Python package build", [executable, "--offline", "build"]),
            GateSpec("package-artifacts", "wheel and source distribution artifacts", "artifact", artifact_patterns=("dist/*.whl", "dist/*.tar.gz"), min_artifacts=2),
        )
        claims = (
            ClaimSpec("library-importable", "The generated Python library imports locally.", "local generated scaffold", ("library-imports",)),
            ClaimSpec("tests-pass", "The generated scaffold unit tests pass locally.", "local generated scaffold", ("unit-tests",)),
            ClaimSpec(
                "pytest-pass",
                "The generated scaffold also passes under pinned pytest.",
                "local generated scaffold",
                ("pytest-tests",),
                False,
            ),
            ClaimSpec("package-builds", "The generated scaffold builds a wheel and source distribution locally.", "local package build", ("package-build", "package-artifacts")),
        )
        return VerificationSuite("python-library", "0.1", "generated Python library bootstrap scaffold", gates, claims, "python", (
            "Public PyPI publication and installation are outside this verification scope.",
            "pytest is additive; unittest remains the required local test gate. Overlay upgrades do not rewrite pyproject.toml to inject pytest.",
        ))

    if suite_id == "node-library":
        gates = (
            _command_gate("library-imports", "generated JavaScript library import", ["node", "--input-type=module", "-e", "import('./src/index.js').then(m => console.log(m.scaffoldStatus()))"], "scaffold ready"),
            _command_gate("unit-tests", "local Node tests", [executable, "test"]),
            _command_gate("package-pack", "local npm package creation", [executable, "pack", "--ignore-scripts"]),
            GateSpec("package-artifact", "npm tarball artifact", "artifact", artifact_patterns=("*.tgz",), min_artifacts=1),
        )
        claims = (
            ClaimSpec("library-importable", "The generated JavaScript library imports locally.", "local generated scaffold", ("library-imports",)),
            ClaimSpec("tests-pass", "The generated Node tests pass locally.", "local generated scaffold", ("unit-tests",)),
            ClaimSpec("package-created", "The generated scaffold can be packed as an npm tarball locally.", "local package build", ("package-pack", "package-artifact")),
        )
        return VerificationSuite("node-library", "0.1", "generated JavaScript library bootstrap scaffold", gates, claims, "node", (
            "Public npm publication and installation are outside this verification scope.",
        ))

    if suite_id == "browser-extension-js":
        gates = (
            _command_gate("manifest-check", "Manifest V3 structure", [executable, "run", "check:manifest"], "manifest ok"),
            _command_gate("module-tests", "local JavaScript smoke tests", [executable, "test"]),
            _command_gate("package-pack", "local extension package creation", [executable, "pack", "--ignore-scripts"]),
            GateSpec("package-artifact", "extension npm tarball artifact", "artifact", artifact_patterns=("*.tgz",), min_artifacts=1),
        )
        claims = (
            ClaimSpec("manifest-structure", "The generated Manifest V3 structure passes the local manifest gate.", "static manifest structure", ("manifest-check",)),
            ClaimSpec("module-tests-pass", "The generated JavaScript smoke tests pass locally.", "local generated scaffold", ("module-tests",)),
            ClaimSpec("package-created", "The generated extension scaffold can be packed locally.", "local package build", ("package-pack", "package-artifact")),
            ClaimSpec("chrome-runtime", "The extension works in a real Chrome runtime.", "Chrome runtime", (), True, "Chrome was not launched by this suite."),
            ClaimSpec("firefox-runtime", "The extension works in a real Firefox runtime.", "Firefox runtime", (), True, "Firefox was not launched by this suite."),
        )
        return VerificationSuite("browser-extension-js", "0.1", "generated JavaScript browser-extension bootstrap scaffold", gates, claims, "node", (
            "Manifest structure, JavaScript tests, and local packaging are checked; real Chrome and Firefox runtime compatibility remain unverified.",
        ))

    if extension_runtime is not None:
        builder = getattr(extension_runtime, "verification_builders", {}).get(suite_id)
        if builder is not None:
            suite = builder(project_name, provider)
            if not isinstance(suite, VerificationSuite):
                raise VerificationError(f"Extension verification builder {suite_id!r} returned an invalid suite.")
            _validate_suite(suite)
            return suite
    raise VerificationError(f"Unknown verification suite: {suite_id}")


def display_verification_commands(suite: VerificationSuite) -> list[list[str]]:
    commands: list[list[str]] = []
    for gate in suite.gates:
        if gate.method != "command":
            continue
        command = list(gate.command)
        if command:
            command[0] = Path(command[0]).name
        commands.append(command)
    return commands


def _execute_command(command: tuple[str, ...], cwd: Path, *, timeout_sec: int = 300) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            list(command),
            cwd=cwd,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "command": list(command),
            "cwd": str(cwd),
            "returncode": 124,
            "stdout": exc.stdout or "",
            "stderr": (exc.stderr or "") + f"\nProject Factory verification command timed out after {timeout_sec}s.",
            "timed_out": True,
            "timeout_sec": timeout_sec,
        }
    return {
        "command": list(command),
        "cwd": str(cwd),
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "timed_out": False,
        "timeout_sec": timeout_sec,
    }


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _evaluate_command_gate(gate: GateSpec, project_root: Path) -> dict[str, Any]:
    raw = _execute_command(gate.command, project_root, timeout_sec=gate.timeout_sec)
    portable = portable_command_result(raw, project_root=project_root)
    combined = (raw["stdout"] or "") + "\n" + (raw["stderr"] or "")
    checks = {
        "returncode_zero": raw["returncode"] == 0,
        "stdout_contains": {value: value in combined for value in gate.expected_stdout_contains},
    }
    passed = checks["returncode_zero"] and all(checks["stdout_contains"].values())
    return {
        "id": gate.id,
        "target": gate.target,
        "method": gate.method,
        "required": gate.required,
        "status": "PASSED" if passed else "FAILED",
        "evidence_level": "PASSED" if passed else "EXECUTED",
        "expected": {"returncode": 0, "output_contains": list(gate.expected_stdout_contains)},
        "observed": portable,
        "checks": checks,
    }


def _evaluate_artifact_gate(gate: GateSpec, project_root: Path) -> dict[str, Any]:
    matched: dict[str, Path] = {}
    for pattern in gate.artifact_patterns:
        for path in project_root.glob(pattern):
            if path.is_file():
                matched[path.relative_to(project_root).as_posix()] = path
    artifacts = [
        {"path": relative, "sha256": _sha256_file(path)} for relative, path in sorted(matched.items())
    ]
    passed = len(artifacts) >= gate.min_artifacts
    return {
        "id": gate.id,
        "target": gate.target,
        "method": gate.method,
        "required": gate.required,
        "status": "PASSED" if passed else "FAILED",
        "evidence_level": "PASSED" if passed else "EXECUTED",
        "expected": {"patterns": list(gate.artifact_patterns), "min_matches": gate.min_artifacts},
        "observed": {"artifacts": artifacts, "match_count": len(artifacts)},
    }


def _probe_environment(suite: VerificationSuite, project_root: Path, provider: ProviderView) -> dict[str, Any]:
    records: dict[str, Any] = {
        "scaffolder": {"id": provider.provider_id, "version": provider.provider_version},
    }
    if suite.runtime_kind == "python":
        raw = _execute_command((provider.executable, "--offline", "run", "python", "--version"), project_root)
        records["runtime"] = {
            "id": "python",
            "version_output": ((raw["stdout"] or raw["stderr"]) or "").strip(),
            "probe_returncode": raw["returncode"],
        }
    elif suite.runtime_kind == "node":
        raw = _execute_command(("node", "--version"), project_root)
        records["runtime"] = {
            "id": "node",
            "version_output": ((raw["stdout"] or raw["stderr"]) or "").strip(),
            "probe_returncode": raw["returncode"],
        }
    return records


def _validate_suite(suite: VerificationSuite) -> None:
    gate_ids = [gate.id for gate in suite.gates]
    if len(gate_ids) != len(set(gate_ids)):
        raise VerificationError(f"Duplicate gate id in suite {suite.id!r}.")
    gate_set = set(gate_ids)
    claim_ids = [claim.id for claim in suite.claims]
    if len(claim_ids) != len(set(claim_ids)):
        raise VerificationError(f"Duplicate claim id in suite {suite.id!r}.")
    for claim in suite.claims:
        missing = [gate_id for gate_id in claim.gate_ids if gate_id not in gate_set]
        if missing:
            raise VerificationError(f"Claim {claim.id!r} references unknown gate(s): {', '.join(missing)}")


def _pytest_declared(project_root: Path) -> bool:
    for name in ("pyproject.toml", "uv.lock"):
        path = project_root / name
        if path.is_file() and "pytest" in path.read_text(encoding="utf-8"):
            return True
    return False


def execute_verification_suite(
    suite: VerificationSuite,
    project_root: Path,
    provider: ProviderView,
) -> dict[str, Any]:
    _validate_suite(suite)
    gate_results: list[dict[str, Any]] = []
    for gate in suite.gates:
        if (
            gate.method == "command"
            and not gate.required
            and gate.id == "pytest-tests"
            and not _pytest_declared(project_root)
        ):
            gate_results.append(
                {
                    "id": gate.id,
                    "target": gate.target,
                    "method": gate.method,
                    "required": False,
                    "status": "FAILED",
                    "evidence_level": "SKIPPED",
                    "expected": {"returncode": 0, "output_contains": list(gate.expected_stdout_contains)},
                    "observed": {"reason": "pytest is not declared in this project."},
                    "checks": {"declared": False},
                }
            )
            continue
        if gate.method == "command":
            gate_results.append(_evaluate_command_gate(gate, project_root))
        elif gate.method == "artifact":
            gate_results.append(_evaluate_artifact_gate(gate, project_root))
        else:
            raise VerificationError(f"Unsupported verification gate method: {gate.method}")

    by_id = {result["id"]: result for result in gate_results}
    claim_results: list[dict[str, Any]] = []
    for claim in suite.claims:
        if not claim.gate_ids:
            status = "UNVERIFIED"
        else:
            referenced = [by_id[gate_id] for gate_id in claim.gate_ids]
            if all(item["status"] == "PASSED" for item in referenced):
                status = "VERIFIED"
            else:
                required_failed = [
                    item for item in referenced if item["status"] != "PASSED" and item.get("required", True)
                ]
                if required_failed:
                    status = "FAILED" if all(item["status"] == "FAILED" for item in referenced) else "PARTIALLY_VERIFIED"
                elif any(item["status"] == "PASSED" for item in referenced):
                    status = "PARTIALLY_VERIFIED"
                else:
                    status = "UNVERIFIED"
        claim_results.append(
            {
                "id": claim.id,
                "statement": claim.statement,
                "scope": claim.scope,
                "status": status,
                "evidence_gates": list(claim.gate_ids),
                "limitation": claim.limitation,
                "material": claim.material,
            }
        )

    required_failures = [
        result["id"] for result in gate_results if result["required"] and result["status"] != "PASSED"
    ]
    material_claims = [claim for claim in claim_results if claim["material"]]
    if required_failures or any(claim["status"] == "FAILED" for claim in material_claims):
        overall = "FAILED"
    elif any(claim["status"] in {"UNVERIFIED", "PARTIALLY_VERIFIED"} for claim in material_claims):
        overall = "PARTIALLY_VERIFIED"
    else:
        overall = "VERIFIED"

    summary = {
        status: sum(1 for claim in claim_results if claim["status"] == status)
        for status in ("VERIFIED", "PARTIALLY_VERIFIED", "UNVERIFIED", "FAILED")
    }
    return {
        "schema_version": "0.1",
        "suite": {"id": suite.id, "version": suite.version},
        "status": overall,
        "scope": suite.scope,
        "required_gates_passed": not required_failures,
        "required_gate_failures": required_failures,
        "gates": gate_results,
        "claims": claim_results,
        "claim_summary": summary,
        "environment": _probe_environment(suite, project_root, provider),
        "limitations": list(suite.limitations),
    }


def assert_required_gates(report: dict[str, Any]) -> None:
    if report.get("required_gates_passed"):
        return
    failures = ", ".join(report.get("required_gate_failures", [])) or "unknown gate failure"
    raise VerificationError(f"Required verification gate(s) failed: {failures}")
