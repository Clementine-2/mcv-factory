from __future__ import annotations

from pathlib import Path


def _audit_formula(blueprint, context, draft, trace):
    draft.evidence_required = True
    trace.append("extension:trusted-lab: audited formula adapter executed")


def _migration(project_root: Path, lock: dict, source_version: str, target_version: str):
    return {
        ".project/extensions/trusted-lab/version.txt": target_version + "\n",
    }


def register(registrar):
    registrar.formula_adapter("trusted-lab.audit-v1", _audit_formula)
    registrar.migration_hook("trusted-lab.migration", _migration)
