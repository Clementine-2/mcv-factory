# P6 Closeout — Harness Compatibility & Process Integration

## Scope completed

P6 implemented a harness-neutral canonical contract plus thin harness adapters and an optional process-integration adapter.

### Canonical agent contract

Generated projects now contain:

- `.project/contract/agent-contract.md` — canonical truth
- `AGENTS.md` — Codex adapter materialization
- `CLAUDE.md` — Claude Code adapter materialization
- `.project/evidence/harness-compatibility.json`

The root harness context files are byte-identical to the canonical contract at generation time. Project Lock records their hashes, and restore verification fails on divergence.

### Spec Kit integration

P6 pins the public process contract to Spec Kit v1.0.1.

Plan-only mode creates:

- `.project/process/spec-kit-plan.json`
- `.project/process/INSTALL.md`
- `.project/evidence/process-integration.json`

Plan-only status is `PLANNED_NOT_INSTALLED`; it never creates `.specify/` or claims runtime installation.

Execute mode is fail-closed: it requires `specify` to exist and report the exact pinned version before mutation. The trusted adapter uses argv lists, not shell command strings, and verifies `.specify/integration.json` plus expected skills directories after execution.

A deterministic test double verifies adapter command sequencing. It is explicitly test evidence, not upstream runtime evidence.

## Automated evidence

P6 baseline: 106 automated tests PASS.

Four Golden projects regenerate and clean-restore with:

- default harness targets: Codex + Claude Code
- harness context status: PARTIALLY_VERIFIED (context parity verified; live harness runtime unverified)
- optional process provider: Spec Kit v1.0.1
- process status: PLANNED_NOT_INSTALLED

Project verification remains:

- Python CLI: VERIFIED
- Python library: VERIFIED
- Node library: VERIFIED
- Browser extension: PARTIALLY_VERIFIED (real Chrome/Firefox runtime remains unverified)

## Packaging evidence

Factory wheel 0.7.0 builds with local installed setuptools using `pip wheel --no-deps --no-build-isolation`.

Wheel package-data inspection confirms harness/process registries and Blueprint schemas are included. The unpacked wheel can generate and restore-verify a Python CLI project outside the source tree.

`uv build --offline` was attempted and failed because setuptools was not present in uv's offline cache. This is an environment/package-cache limitation, not recorded as a successful build path.

## External runtime limitation

At closeout the execution environment reports:

- `codex`: unavailable
- `claude`: unavailable
- `specify`: unavailable

An attempt to install `specify-cli==1.0.1` failed because DNS/PyPI access is unavailable. Therefore real harness sessions and real Spec Kit CLI installation remain UNVERIFIED.
