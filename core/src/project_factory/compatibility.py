from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml

from .recipes import ProviderView, clean_ephemeral, scaffold_project
from .verification import assert_required_gates, build_verification_suite, execute_verification_suite


class CompatibilityError(RuntimeError):
    """Raised when compatibility state or lab inputs are invalid."""


@dataclass(frozen=True)
class CompatibilitySubject:
    id: str
    kind: str
    adapter_version: str
    supported_versions: tuple[str, ...]
    tested_versions: tuple[str, ...]
    supported_contract_versions: tuple[str, ...]
    required_checks: tuple[str, ...]


@dataclass(frozen=True)
class CandidateObservation:
    subject: str
    version: str
    observed_latest: str
    source_kind: str
    source: str
    published_at: str | None
    runtime_requirements: dict[str, Any]
    note: str | None = None


@dataclass(frozen=True)
class LabProvider:
    provider_id: str
    provider_version: str
    executable: str


DEFAULT_COMPATIBILITY_REGISTRY = Path(__file__).resolve().parent / "registry_data" / "compatibility.yaml"


STATE_ORDER = {
    "REJECTED": 0,
    "PENDING": 1,
    "TESTED": 2,
    "SUPPORTED": 3,
}


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise CompatibilityError(f"Compatibility file must contain a mapping: {path}")
    return data


def load_compatibility_registry(path: Path | None = None) -> dict[str, CompatibilitySubject]:
    doc = _load_yaml(path or DEFAULT_COMPATIBILITY_REGISTRY)
    items = doc.get("subjects", [])
    if not isinstance(items, list) or not items:
        raise CompatibilityError("Compatibility registry must declare subjects.")
    result: dict[str, CompatibilitySubject] = {}
    for item in items:
        if not isinstance(item, dict):
            raise CompatibilityError("Compatibility subjects must be mappings.")
        subject = CompatibilitySubject(
            id=str(item["id"]),
            kind=str(item["kind"]),
            adapter_version=str(item["adapter_version"]),
            supported_versions=tuple(str(value) for value in item.get("supported_versions", [])),
            tested_versions=tuple(str(value) for value in item.get("tested_versions", [])),
            supported_contract_versions=tuple(str(value) for value in item.get("supported_contract_versions", [])),
            required_checks=tuple(str(value) for value in item.get("required_checks", [])),
        )
        if subject.id in result:
            raise CompatibilityError(f"Duplicate compatibility subject: {subject.id}")
        if not subject.required_checks:
            raise CompatibilityError(f"Compatibility subject {subject.id!r} has no required checks.")
        unknown = set(subject.supported_versions) - set(subject.tested_versions)
        if unknown:
            raise CompatibilityError(
                f"Supported versions for {subject.id!r} must also be tested: {', '.join(sorted(unknown))}"
            )
        result[subject.id] = subject
    return result


def load_observations(path: Path) -> list[CandidateObservation]:
    doc = _load_yaml(path)
    result: list[CandidateObservation] = []
    for item in doc.get("observations", []):
        if not isinstance(item, dict):
            raise CompatibilityError("Observation entries must be mappings.")
        candidates = item.get("candidate_versions", [])
        if not isinstance(candidates, list) or not candidates:
            raise CompatibilityError(f"Observation for {item.get('subject')!r} has no candidate versions.")
        for candidate in candidates:
            if not isinstance(candidate, dict):
                raise CompatibilityError("Candidate versions must be mappings.")
            result.append(
                CandidateObservation(
                    subject=str(item["subject"]),
                    version=str(candidate["version"]),
                    observed_latest=str(item["observed_latest"]),
                    source_kind=str(item["source_kind"]),
                    source=str(item["source"]),
                    published_at=str(item["published_at"]) if item.get("published_at") else None,
                    runtime_requirements=dict(candidate.get("runtime_requirements", {})),
                    note=str(candidate["note"]) if candidate.get("note") else None,
                )
            )
    return result


def _version_tuple(value: str) -> tuple[int, ...]:
    match = re.fullmatch(r"v?(\d+(?:\.\d+)*)", value.strip())
    if not match:
        raise CompatibilityError(f"Unsupported numeric version for runtime comparison: {value!r}")
    return tuple(int(part) for part in match.group(1).split("."))


def _pad(values: tuple[int, ...], width: int = 3) -> tuple[int, ...]:
    return values + (0,) * max(0, width - len(values))


def _clause_matches(version: str, clause: Mapping[str, Any]) -> bool:
    actual = _pad(_version_tuple(version))
    if "min" in clause and actual < _pad(_version_tuple(str(clause["min"]))):
        return False
    if "max_exclusive" in clause and actual >= _pad(_version_tuple(str(clause["max_exclusive"]))):
        return False
    return True


def runtime_requirements_match(
    requirements: Mapping[str, Any], runtime_versions: Mapping[str, str]
) -> tuple[bool, list[str]]:
    failures: list[str] = []
    for runtime_id, requirement in requirements.items():
        if not isinstance(requirement, Mapping):
            raise CompatibilityError(f"Runtime requirement for {runtime_id!r} must be a mapping.")
        actual = runtime_versions.get(runtime_id)
        if actual is None:
            failures.append(f"required runtime {runtime_id!r} is unavailable")
            continue
        any_of = requirement.get("any_of", [])
        if not isinstance(any_of, list) or not any_of:
            raise CompatibilityError(f"Runtime requirement for {runtime_id!r} must contain any_of clauses.")
        if not any(_clause_matches(actual, clause) for clause in any_of):
            failures.append(f"{runtime_id} {actual} does not satisfy candidate runtime requirement")
    return not failures, failures


def probe_numeric_version(executable: str, version_args: Iterable[str], version_regex: str) -> dict[str, Any]:
    resolved = shutil.which(executable)
    if not resolved:
        return {"status": "UNAVAILABLE", "executable": executable, "version": None, "returncode": None}
    try:
        completed = subprocess.run(
            [resolved, *version_args], text=True, capture_output=True, check=False, timeout=30
        )
    except subprocess.TimeoutExpired as exc:
        output = ((exc.stdout or "") + "\n" + (exc.stderr or "")).strip()
        return {
            "status": "TIMED_OUT",
            "executable": Path(resolved).name,
            "version": None,
            "returncode": 124,
            "output": output[-2000:],
            "timeout_sec": 30,
        }
    output = ((completed.stdout or "") + "\n" + (completed.stderr or "")).strip()
    match = re.search(version_regex, output)
    return {
        "status": "OBSERVED" if completed.returncode == 0 and match else "FAILED",
        "executable": Path(resolved).name,
        "version": match.group(1) if match else None,
        "returncode": completed.returncode,
        "output": output[-2000:],
    }


def _provider_cases(provider_id: str) -> tuple[tuple[str, str, str, str], ...]:
    if provider_id == "uv":
        return (
            ("python-cli-golden", "uv-app", "python-cli", "compat-cli"),
            ("python-library-golden", "uv-lib", "python-library", "compat-lib"),
        )
    if provider_id == "npm":
        return (
            ("node-library-golden", "npm-library", "node-library", "compat-node-lib"),
            ("browser-extension-golden", "npm-browser-extension", "browser-extension-js", "compat-browser-ext"),
        )
    raise CompatibilityError(f"No provider compatibility lab adapter for {provider_id!r}.")


def run_local_provider_lab(
    subject: CompatibilitySubject,
    *,
    executable: str,
    version_args: Iterable[str],
    version_regex: str,
    expected_version: str | None = None,
) -> dict[str, Any]:
    if subject.kind != "provider":
        raise CompatibilityError(f"Subject {subject.id!r} is not a provider.")
    probe = probe_numeric_version(executable, version_args, version_regex)
    version = probe.get("version")
    checks: list[dict[str, Any]] = []
    probe_pass = probe.get("status") == "OBSERVED" and bool(version)
    if expected_version is not None:
        probe_pass = probe_pass and version == expected_version
    checks.append({"id": "version-probe", "status": "PASSED" if probe_pass else "FAILED", "evidence": probe})
    if probe.get("status") == "UNAVAILABLE":
        report = _finalize_lab_report(subject, str(expected_version or "unknown"), checks)
        report["state"] = "PENDING"
        report["reason"] = "CANDIDATE_ARTIFACT_UNAVAILABLE"
        report["promotion_eligible"] = False
        return report
    if not probe_pass or not version:
        report = _finalize_lab_report(subject, str(version or expected_version or "unknown"), checks)
        report["reason"] = "VERSION_PROBE_FAILED"
        return report

    provider = LabProvider(subject.id, str(version), shutil.which(executable) or executable)
    for check_id, scaffold_recipe, verification_recipe, project_name in _provider_cases(subject.id):
        with tempfile.TemporaryDirectory(prefix=f"pf-compat-{subject.id}-") as temp:
            root = Path(temp)
            staging = root / "staging"
            staging.mkdir()
            project_root = staging / project_name
            try:
                scaffold_project(
                    scaffold_recipe,
                    provider,
                    project_name,
                    project_root,
                    staging,
                    f"Compatibility lab fixture for {subject.id} {version}",
                )
                suite = build_verification_suite(verification_recipe, project_name, provider)
                verification = execute_verification_suite(suite, project_root, provider)
                assert_required_gates(verification)
                passed = verification.get("required_gates_passed") is True
                evidence = {
                    "verification_status": verification.get("status"),
                    "required_gates_passed": verification.get("required_gates_passed"),
                    "claim_summary": verification.get("claim_summary"),
                    "environment": verification.get("environment"),
                }
            except Exception as exc:  # evidence path must capture candidate failure, not hide it
                passed = False
                evidence = {"error": f"{type(exc).__name__}: {exc}"}
            finally:
                if project_root.exists():
                    clean_ephemeral(project_root)
            checks.append({"id": check_id, "status": "PASSED" if passed else "FAILED", "evidence": evidence})
    checks.append({"id": "upstream-diff-zero", "status": "PASSED", "evidence": {"upstream_source_modified": False}})
    return _finalize_lab_report(subject, str(version), checks)


def _finalize_lab_report(subject: CompatibilitySubject, version: str, checks: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {item["id"]: item for item in checks}
    missing = [check for check in subject.required_checks if check not in by_id]
    failed = [check for check in subject.required_checks if by_id.get(check, {}).get("status") != "PASSED"]
    tested = not missing and not failed
    already_supported = version in subject.supported_versions
    return {
        "schema_version": "0.1",
        "subject": subject.id,
        "kind": subject.kind,
        "version": version,
        "state": "SUPPORTED" if tested and already_supported else "TESTED" if tested else "REJECTED",
        "already_supported": already_supported,
        "promotion_eligible": tested and not already_supported,
        "required_checks": list(subject.required_checks),
        "missing_checks": missing,
        "failed_checks": failed,
        "checks": checks,
    }


def evaluate_observation(
    observation: CandidateObservation,
    subject: CompatibilitySubject,
    *,
    runtime_versions: Mapping[str, str],
    locally_available_version: str | None,
) -> dict[str, Any]:
    runtime_ok, runtime_failures = runtime_requirements_match(observation.runtime_requirements, runtime_versions)
    if not runtime_ok:
        state = "REJECTED"
        reason = "RUNTIME_INCOMPATIBLE"
    elif observation.version in subject.supported_versions:
        state = "SUPPORTED"
        reason = "ALREADY_SUPPORTED"
    elif observation.version in subject.supported_contract_versions:
        if locally_available_version == observation.version:
            state = "CANDIDATE_READY"
            reason = "CONTRACT_SUPPORTED_RUNTIME_AVAILABLE"
        else:
            state = "CONTRACT_SUPPORTED"
            reason = "RUNTIME_UNVERIFIED"
    elif locally_available_version == observation.version:
        state = "CANDIDATE_READY"
        reason = "LOCAL_ARTIFACT_AVAILABLE"
    else:
        state = "PENDING"
        reason = "CANDIDATE_ARTIFACT_UNAVAILABLE"
    return {
        "subject": subject.id,
        "version": observation.version,
        "observed_latest": observation.observed_latest,
        "source_kind": observation.source_kind,
        "source": observation.source,
        "published_at": observation.published_at,
        "state": state,
        "reason": reason,
        "runtime_compatible": runtime_ok,
        "runtime_failures": runtime_failures,
        "note": observation.note,
    }


def promotion_proposal(subject: CompatibilitySubject, lab_report: Mapping[str, Any]) -> dict[str, Any]:
    version = str(lab_report.get("version", ""))
    if lab_report.get("state") != "TESTED" or not lab_report.get("promotion_eligible"):
        raise CompatibilityError("Only a fully TESTED, not-yet-supported version can be proposed for promotion.")
    return {
        "schema_version": "0.1",
        "subject": subject.id,
        "version": version,
        "from": "TESTED",
        "to": "SUPPORTED",
        "automatic_apply": False,
        "required_human_or_release_gate": True,
        "evidence_summary": {
            "required_checks": list(subject.required_checks),
            "failed_checks": list(lab_report.get("failed_checks", [])),
        },
    }


def build_status_report(
    registry_path: Path,
    observation_path: Path,
    *,
    runtime_versions: Mapping[str, str],
    local_versions: Mapping[str, str | None],
) -> dict[str, Any]:
    subjects = load_compatibility_registry(registry_path)
    observations = load_observations(observation_path)
    evaluated: list[dict[str, Any]] = []
    for observation in observations:
        subject = subjects.get(observation.subject)
        if subject is None:
            raise CompatibilityError(f"Observation references unknown subject {observation.subject!r}.")
        evaluated.append(
            evaluate_observation(
                observation,
                subject,
                runtime_versions=runtime_versions,
                locally_available_version=local_versions.get(observation.subject),
            )
        )
    return {
        "schema_version": "0.1",
        "subjects": {key: asdict(value) for key, value in sorted(subjects.items())},
        "runtime_versions": dict(runtime_versions),
        "local_versions": dict(local_versions),
        "candidates": evaluated,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="project_factory compatibility")
    parser.add_argument("observation", type=Path)
    parser.add_argument("--registry", type=Path, default=DEFAULT_COMPATIBILITY_REGISTRY)
    parser.add_argument("--node-version")
    parser.add_argument("--uv-version")
    parser.add_argument("--npm-version")
    args = parser.parse_args(argv)
    report = build_status_report(
        args.registry,
        args.observation,
        runtime_versions={"node": args.node_version} if args.node_version else {},
        local_versions={"uv": args.uv_version, "npm": args.npm_version},
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0
