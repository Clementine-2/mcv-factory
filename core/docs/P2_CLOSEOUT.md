# P2 Minimal Vertical Slice Closeout

## Status

P2 is COMPLETE only for the single supported vertical slice: natural-language requirement -> Python CLI Blueprint -> minimal execution decision -> python-cli profile -> `project_scaffolding` capability -> `uv` provider -> native project -> verification -> Project Lock -> project ZIP -> clean restore verification.

## What P2 proves

- The Factory can materially produce a native project, not only describe one.
- Blueprint remains provider-neutral.
- Provider selection happens after Capability resolution.
- `uv` is used through its public CLI; upstream source is not copied or modified.
- A minimal project receives a small overlay rather than a large framework tree.
- The Factory creates only a bootstrap scaffold. It does not implement domain-specific product behavior.
- Generated projects can be independently extracted, manifest-verified, run, unit-tested, and built.
- Missing or materially unresolved requirements block materialization.
- Existing output is never overwritten silently.

## Current P2 supported profile

`python-cli@0.1`

Current capability set:

- `project_scaffolding`

Current tested provider in this checkpoint:

- `uv 0.10.0`

This is a tested provider version, not a claim that it is the latest upstream version.

## Generated minimal overlay

The Golden Project contains:

- `AGENTS.md`
- `project.lock.json`
- `.project/blueprint.yaml`
- `.project/blueprint.meta.yaml`
- `.project/generation.json`
- `.project/evidence/generation-verification.json`
- `PROJECT_MANIFEST.sha256`

alongside the native Python package structure produced from `uv init --app --package` and then minimally customized for the project contract.

## Verification gates

The generated Golden Project is verified by:

1. `uv --offline run <project-name>`
2. `uv --offline run <project-name> --version`
3. `uv --offline run python -m unittest discover -s tests -v`
4. `uv --offline build`
5. Project manifest verification
6. ZIP CRC verification
7. Clean extraction and repetition of gates 1-5

## Deliberately not implemented

- business-specific feature implementation
- production LLM semantic normalizer
- general Formula engine
- registry-driven multi-profile selection
- Copier integration
- Spec Kit integration
- web/browser/research project generation
- Harness adapters
- Runner/AionUI integration
- existing-project upgrade
- GUI

## Architectural observation

P2 provides concrete evidence for the already-frozen `Native Ecosystem First` rule. For a Python CLI, a native mature scaffolder (`uv`) is sufficient; Copier should remain a future overlay/fallback capability rather than being forced into every project.
