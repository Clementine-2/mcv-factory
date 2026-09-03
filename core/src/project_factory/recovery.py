from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any


class RecoveryError(RuntimeError):
    """Raised when a checkpoint archive cannot be verified or restored safely."""


CHECKPOINT_ZIP_MAX_FILES = 100_000
CHECKPOINT_ZIP_MAX_MEMBER_BYTES = 2 * 1024 * 1024 * 1024
CHECKPOINT_ZIP_MAX_TOTAL_BYTES = 8 * 1024 * 1024 * 1024


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _safe_member(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if not name or "\\" in name or path.is_absolute() or ".." in path.parts or "" in path.parts:
        raise RecoveryError(f"Unsafe checkpoint ZIP member: {name!r}")
    return path


def _assert_regular_member(info: zipfile.ZipInfo) -> None:
    mode = info.external_attr >> 16
    if mode and stat.S_ISLNK(mode):
        raise RecoveryError(f"Checkpoint symbolic-link member is not allowed: {info.filename!r}")


def _manifest_entries(data: bytes) -> dict[str, str]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RecoveryError("Checkpoint MANIFEST.sha256 is not UTF-8 text.") from exc
    result: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            digest, relative = line.split("  ", 1)
        except ValueError as exc:
            raise RecoveryError(f"Malformed checkpoint manifest line: {line!r}") from exc
        if len(digest) != 64 or any(char not in "0123456789abcdefABCDEF" for char in digest):
            raise RecoveryError(f"Malformed SHA256 digest in checkpoint manifest: {digest!r}")
        safe = _safe_member(relative).as_posix()
        if safe in result:
            raise RecoveryError(f"Duplicate checkpoint manifest path: {safe}")
        result[safe] = digest.casefold()
    if not result:
        raise RecoveryError("Checkpoint MANIFEST.sha256 is empty.")
    return result


def _top_level_prefix(names: list[str]) -> str:
    roots = {PurePosixPath(name).parts[0] for name in names if PurePosixPath(name).parts}
    if len(roots) != 1:
        raise RecoveryError("Checkpoint ZIP must contain exactly one top-level directory.")
    return next(iter(roots))


def inspect_checkpoint(zip_path: Path, *, expected_zip_sha256: str | None = None) -> dict[str, Any]:
    zip_path = Path(zip_path).resolve()
    if not zip_path.is_file():
        raise RecoveryError(f"Checkpoint ZIP does not exist: {zip_path}")
    outer_sha = _sha256_file(zip_path)
    if expected_zip_sha256 and outer_sha.casefold() != expected_zip_sha256.casefold():
        raise RecoveryError("Checkpoint ZIP SHA256 does not match the expected digest.")
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            bad = archive.testzip()
            if bad is not None:
                raise RecoveryError(f"Checkpoint ZIP CRC failed at member: {bad}")
            file_names: list[str] = []
            members: dict[str, zipfile.ZipInfo] = {}
            total_size = 0
            for info in archive.infolist():
                safe = _safe_member(info.filename)
                _assert_regular_member(info)
                name = safe.as_posix()
                if info.is_dir():
                    continue
                if info.file_size > CHECKPOINT_ZIP_MAX_MEMBER_BYTES:
                    raise RecoveryError(f"Checkpoint ZIP member exceeds safe size limit: {name}")
                total_size += info.file_size
                if total_size > CHECKPOINT_ZIP_MAX_TOTAL_BYTES:
                    raise RecoveryError("Checkpoint ZIP exceeds safe total uncompressed size limit.")
                if name in members:
                    raise RecoveryError(f"Duplicate checkpoint ZIP member: {name}")
                members[name] = info
                file_names.append(name)
                if len(file_names) > CHECKPOINT_ZIP_MAX_FILES:
                    raise RecoveryError("Checkpoint ZIP contains too many files.")
            prefix = _top_level_prefix(file_names)
            manifest_name = f"{prefix}/MANIFEST.sha256"
            if manifest_name not in members:
                raise RecoveryError("Checkpoint ZIP is missing MANIFEST.sha256.")
            manifest = _manifest_entries(archive.read(members[manifest_name]))
            failures: list[str] = []
            for relative, expected in sorted(manifest.items()):
                member_name = f"{prefix}/{relative}"
                info = members.get(member_name)
                if info is None:
                    failures.append(f"missing:{relative}")
                    continue
                actual = _sha256_bytes(archive.read(info))
                if actual != expected:
                    failures.append(f"sha256:{relative}")
            checkpoint_candidates = [
                name for name in members if name.startswith(f"{prefix}/CHECKPOINT_") and name.endswith(".md")
            ]
            def checkpoint_rank(name: str) -> tuple[int, str]:
                if re.search(r"/CHECKPOINT_PINF(?:_|\.)", name, flags=re.IGNORECASE):
                    return (1_000_000, name)
                match = re.search(r"/CHECKPOINT_P(\d+)(?:_|\.)", name)
                return (int(match.group(1)) if match else -1, name)
            checkpoint_file = max(checkpoint_candidates, key=checkpoint_rank) if checkpoint_candidates else None
    except zipfile.BadZipFile as exc:
        raise RecoveryError("Checkpoint file is not a valid ZIP archive.") from exc
    return {
        "schema_version": "0.1",
        "status": "VERIFIED" if not failures else "FAILED",
        "zip": str(zip_path),
        "zip_sha256": outer_sha,
        "zip_crc": "PASS",
        "top_level_directory": prefix,
        "manifest_entries": len(manifest),
        "manifest_failures": failures,
        "archive_files": len(file_names),
        "checkpoint_metadata_file": checkpoint_file,
    }


@dataclass(frozen=True)
class CheckpointRestorePlan:
    schema_version: str
    zip_path: str
    zip_sha256: str
    destination: str
    top_level_directory: str
    manifest_entries: int
    archive_files: int
    status: str
    plan_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def plan_checkpoint_restore(zip_path: Path, out_dir: Path) -> CheckpointRestorePlan:
    inspection = inspect_checkpoint(zip_path)
    if inspection["status"] != "VERIFIED":
        raise RecoveryError("Checkpoint inspection failed; restore is blocked.")
    destination = Path(out_dir).resolve()
    if destination.exists():
        raise RecoveryError("Restore destination already exists; refusing to overwrite or merge.")
    payload = {
        "schema_version": "0.1",
        "zip_path": str(Path(zip_path).resolve()),
        "zip_sha256": inspection["zip_sha256"],
        "destination": str(destination),
        "top_level_directory": inspection["top_level_directory"],
        "manifest_entries": inspection["manifest_entries"],
        "archive_files": inspection["archive_files"],
        "status": "READY",
    }
    return CheckpointRestorePlan(plan_sha256=_sha256_bytes(_json_bytes(payload)), **payload)


def _write_member(archive: zipfile.ZipFile, info: zipfile.ZipInfo, destination: Path) -> None:
    safe = _safe_member(info.filename)
    _assert_regular_member(info)
    target = destination.joinpath(*safe.parts)
    resolved = target.resolve()
    root = destination.resolve()
    if os.path.commonpath((str(root), str(resolved))) != str(root):
        raise RecoveryError(f"Checkpoint member escapes destination: {info.filename!r}")
    if info.is_dir():
        resolved.mkdir(parents=True, exist_ok=True)
        return
    resolved.parent.mkdir(parents=True, exist_ok=True)
    if resolved.exists():
        raise RecoveryError(f"Refusing to overwrite restored file: {resolved}")
    with archive.open(info, "r") as source, resolved.open("xb") as target_handle:
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            target_handle.write(chunk)


def _verify_extracted_manifest(destination: Path, prefix: str) -> dict[str, Any]:
    root = destination / prefix
    manifest_path = root / "MANIFEST.sha256"
    if not manifest_path.is_file():
        raise RecoveryError("Restored checkpoint is missing MANIFEST.sha256.")
    manifest = _manifest_entries(manifest_path.read_bytes())
    failures: list[str] = []
    for relative, expected in sorted(manifest.items()):
        path = root / Path(relative)
        if not path.is_file():
            failures.append(f"missing:{relative}")
            continue
        if _sha256_file(path) != expected:
            failures.append(f"sha256:{relative}")
    return {
        "status": "PASS" if not failures else "FAILED",
        "entries": len(manifest),
        "failures": failures,
    }


def apply_checkpoint_restore(
    zip_path: Path,
    out_dir: Path,
    *,
    confirm_plan_sha256: str,
) -> dict[str, Any]:
    plan = plan_checkpoint_restore(zip_path, out_dir)
    if confirm_plan_sha256.casefold() != plan.plan_sha256.casefold():
        raise RecoveryError("Restore confirmation hash does not match the current DryRun plan.")
    destination = Path(plan.destination)
    destination.mkdir(parents=True, exist_ok=False)
    try:
        with zipfile.ZipFile(Path(zip_path).resolve(), "r") as archive:
            for info in archive.infolist():
                _write_member(archive, info, destination)
        verified = _verify_extracted_manifest(destination, plan.top_level_directory)
        if verified["status"] != "PASS":
            raise RecoveryError("Restored checkpoint failed MANIFEST verification.")
    except Exception:
        # Do not delete the destination automatically. A partial extraction is evidence and
        # auto-deletion would violate the project's no-unrequested-delete rule.
        raise
    return {
        "schema_version": "0.1",
        "status": "RESTORED",
        "destination": str(destination),
        "project_root": str(destination / plan.top_level_directory),
        "zip_sha256": plan.zip_sha256,
        "plan_sha256": plan.plan_sha256,
        "manifest": verified,
        "overwrite_performed": False,
        "automatic_delete_on_failure": False,
        "undo": "Destination was newly created. If rollback is required, inspect it first and remove it explicitly; Project Factory does not auto-delete restored data.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect or restore Project Factory checkpoint ZIPs")
    sub = parser.add_subparsers(dest="command", required=True)
    inspect_p = sub.add_parser("inspect", help="Read-only CRC/SHA256/MANIFEST checkpoint inspection")
    inspect_p.add_argument("zip_path", type=Path)
    inspect_p.add_argument("--expected-zip-sha256")
    plan_p = sub.add_parser("plan", help="DryRun a restore into a new destination")
    plan_p.add_argument("zip_path", type=Path)
    plan_p.add_argument("--out-dir", required=True, type=Path)
    apply_p = sub.add_parser("restore", help="Apply an exact restore plan into a new destination")
    apply_p.add_argument("zip_path", type=Path)
    apply_p.add_argument("--out-dir", required=True, type=Path)
    apply_p.add_argument("--confirm-plan-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            result = inspect_checkpoint(args.zip_path, expected_zip_sha256=args.expected_zip_sha256)
            code = 0 if result["status"] == "VERIFIED" else 2
        elif args.command == "plan":
            result = plan_checkpoint_restore(args.zip_path, args.out_dir).to_dict()
            code = 0
        else:
            result = apply_checkpoint_restore(
                args.zip_path,
                args.out_dir,
                confirm_plan_sha256=args.confirm_plan_sha256,
            )
            code = 0
    except (RecoveryError, OSError, zipfile.BadZipFile) as exc:
        result = {"status": "BLOCKED", "error": str(exc)}
        code = 4
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
