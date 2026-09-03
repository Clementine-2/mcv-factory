# P7 Upstream Observation Evidence — 2026-08-30

This document records the external facts normalized into `compatibility/observations/2026-08-30.yaml`.

These are observations, not automatic support decisions.

## uv

Observed upstream release:

- version: `0.12.7`
- published: 2026-08-27
- source: https://github.com/astral-sh/uv/releases/tag/0.12.7

Current local lab runtime:

- uv: `0.10.0`

P7 result:

- `0.10.0`: revalidated locally, remains `SUPPORTED`.
- `0.12.7`: `PENDING`; the current execution environment did not contain/download the exact candidate artifact, so it was not promoted to TESTED.

## npm CLI

Observed top-level npm CLI release:

- version: `12.0.2`
- release: https://github.com/npm/cli/releases/tag/v12.0.2
- upstream `package.json` engine contract at tag v12.0.2:
  `^22.22.2 || ^24.15.0 || >=26.0.0`

Current local runtime:

- Node: `22.16.0`
- npm: `10.9.2`

Because Node 22.16.0 is below the v12 Node 22 floor of 22.22.2, npm 12.0.2 is marked `REJECTED / RUNTIME_INCOMPATIBLE` for this lab environment. This is not recorded as an npm defect.

A second observed candidate for the Node 22-compatible npm 10 line:

- version: `10.9.9`
- release: https://github.com/npm/cli/releases/tag/v10.9.9
- engine contract: `^18.17.0 || >=20.5.0`

P7 result:

- `10.9.2`: revalidated locally, remains `SUPPORTED`.
- `10.9.9`: runtime-eligible but `PENDING` because the exact candidate artifact was not available for isolated execution.
- `12.0.2`: `REJECTED` for the current Node runtime.

## Spec Kit

Observed upstream release:

- version: `1.0.1`
- published: 2026-08-21
- source: https://github.com/github/spec-kit/releases/tag/v1.0.1

P6 already pinned and audited the public Codex/Claude integration contract at v1.0.1.

Current environment:

- `specify`: unavailable.

P7 result:

- contract: `CONTRACT_SUPPORTED`;
- live runtime: `RUNTIME_UNVERIFIED`;
- no promotion to runtime-supported.

## Codex / Claude Code

P6 established canonical context adapters for Codex and Claude Code based on pinned public contracts.

Current environment:

- `codex`: unavailable;
- `claude`: unavailable.

P7 result:

- contract snapshots remain `CONTRACT_SUPPORTED`;
- live runtime remains `RUNTIME_UNVERIFIED`.

## Important evidence boundary

No candidate was promoted merely because it was newer.

The dated observation snapshot is intentionally outside the durable compatibility Registry.
