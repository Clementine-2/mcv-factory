"""Factory overlay plugin.

Copier is the overlay *drawing*: answers file, exclude list, template refresh.
The kernel does not depend on the Copier package. `copier update` needs a
git-tracked destination and a stored template path; Factory-generated projects
are not required to be git repos, and the template lives inside the current
wheel. Refresh always copies from the packaged template of this Factory version.

This plugin writes only the overlay allowlist. Language roots (uv/npm) and
user source trees are out of scope.
"""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

import yaml


class OverlayError(RuntimeError):
    """Raised when the Factory overlay cannot be applied safely."""


TEMPLATE_SRC_PATH = "project-factory://overlay"
ANSWERS_RELATIVE = ".copier-answers.factory-overlay.yml"
SKILL_RELATIVE = "skills/factory-discipline/SKILL.md"
SPINE_RELATIVE = ".project/overlay/VERIFICATION_SPINE.md"

OVERLAY_MANAGED_PATHS = (
    SKILL_RELATIVE,
    SPINE_RELATIVE,
    ANSWERS_RELATIVE,
)

TEMPLATE_DESTINATIONS = {
    "skills/factory-discipline/SKILL.md.jinja": SKILL_RELATIVE,
    "VERIFICATION_SPINE.md.jinja": SPINE_RELATIVE,
}

_FORBIDDEN_PREFIXES = ("src/", "tests/")
_FORBIDDEN_NAMES = frozenset(
    {
        "pyproject.toml",
        "package.json",
        "package-lock.json",
        "uv.lock",
        "manifest.json",
        "wxt.config.ts",
    }
)
_VAR = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


def template_root() -> Path:
    return Path(__file__).resolve().parent / "template"


def overlay_context(
    *,
    project_name: str,
    profile_id: str,
    factory_version: str,
) -> dict[str, str]:
    return {
        "project_name": str(project_name),
        "profile_id": str(profile_id),
        "factory_version": str(factory_version),
    }


def destination_is_forbidden(relative: str) -> bool:
    rel = relative.replace("\\", "/")
    if not rel or rel.startswith("/") or ".." in PurePosixPath(rel).parts:
        return True
    if rel in _FORBIDDEN_NAMES or rel.rsplit("/", 1)[-1] in _FORBIDDEN_NAMES:
        return True
    return rel.startswith(_FORBIDDEN_PREFIXES)


def _render_text(template: str, data: Mapping[str, str]) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in data:
            raise OverlayError(f"Unknown overlay template variable: {key}")
        return data[key]

    return _VAR.sub(repl, template)


def _answers_bytes(data: Mapping[str, str]) -> bytes:
    payload = {
        "_commit": data["factory_version"],
        "_src_path": TEMPLATE_SRC_PATH,
        "factory_version": data["factory_version"],
        "project_name": data["project_name"],
        "profile_id": data["profile_id"],
    }
    body = yaml.safe_dump(
        payload,
        sort_keys=True,
        allow_unicode=True,
        default_flow_style=False,
    )
    header = "# Changes here will be overwritten by Factory overlay refresh. Do not edit by hand.\n"
    return (header + body).encode("utf-8")


def _load_copier_config() -> dict[str, Any]:
    path = template_root() / "copier.yml"
    if not path.is_file():
        raise OverlayError("Packaged overlay template is missing copier.yml.")
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise OverlayError("Overlay copier.yml must be a mapping.")
    answers = str(loaded.get("_answers_file", "")).strip()
    if answers != ANSWERS_RELATIVE:
        raise OverlayError(f"Overlay answers file must be {ANSWERS_RELATIVE}, got {answers!r}.")
    exclude = loaded.get("_exclude") or []
    required_exclude = {"src", "tests", "pyproject.toml", "package.json"}
    missing = required_exclude.difference(str(item) for item in exclude)
    if missing:
        raise OverlayError("Overlay copier.yml exclude is missing: " + ", ".join(sorted(missing)))
    return loaded


def render_overlay_targets(
    *,
    project_name: str,
    profile_id: str,
    factory_version: str,
) -> dict[str, bytes]:
    """Render Factory overlay files from the packaged template. Never includes source trees."""
    _load_copier_config()
    data = overlay_context(
        project_name=project_name,
        profile_id=profile_id,
        factory_version=factory_version,
    )
    root = template_root()
    rendered: dict[str, bytes] = {}
    for template_relative, destination in TEMPLATE_DESTINATIONS.items():
        if destination_is_forbidden(destination) or destination not in OVERLAY_MANAGED_PATHS:
            raise OverlayError(f"Overlay destination is not allowlisted: {destination}")
        source = root / template_relative
        if not source.is_file():
            raise OverlayError(f"Packaged overlay template is missing {template_relative}.")
        text = _render_text(source.read_text(encoding="utf-8"), data)
        if not text.endswith("\n"):
            text += "\n"
        rendered[destination] = text.replace("\r\n", "\n").encode("utf-8")
    rendered[ANSWERS_RELATIVE] = _answers_bytes(data)
    missing = set(OVERLAY_MANAGED_PATHS) - set(rendered)
    if missing:
        raise OverlayError("Overlay render missed: " + ", ".join(sorted(missing)))
    extra = set(rendered) - set(OVERLAY_MANAGED_PATHS)
    if extra:
        raise OverlayError("Overlay render produced extra paths: " + ", ".join(sorted(extra)))
    for relative in rendered:
        if destination_is_forbidden(relative):
            raise OverlayError(f"Overlay refused to write forbidden path: {relative}")
    return rendered


def apply_factory_overlay(
    project_root: Path,
    *,
    project_name: str,
    profile_id: str,
    factory_version: str,
    extra_profile_ids: tuple[str, ...] = (),
) -> tuple[str, ...]:
    """Write Factory overlay files into an already-scaffolded project.

    uv/npm (or other language-root) files are not rewritten. Missing overlay
    files are created; existing overlay allowlist files are refreshed.
    """
    root = Path(project_root)
    if not root.is_dir():
        raise OverlayError(f"Cannot apply overlay; project root is missing: {root}")
    targets = render_overlay_targets(
        project_name=project_name,
        profile_id=profile_id,
        factory_version=factory_version,
    )
    written: list[str] = []
    for relative, payload in targets.items():
        if destination_is_forbidden(relative):
            raise OverlayError(f"Overlay refused to write forbidden path: {relative}")
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        written.append(relative)
    extra_ids = extra_profile_ids or ()
    from ..assembly import render_profile_skill

    for pid in (profile_id, *extra_ids):
        relative = f"skills/{pid}/SKILL.md"
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        text = render_profile_skill(project_name, pid, factory_version)
        if not text.endswith("\n"):
            text += "\n"
        path.write_bytes(text.replace("\r\n", "\n").encode("utf-8"))
        written.append(relative)
    return tuple(written)
