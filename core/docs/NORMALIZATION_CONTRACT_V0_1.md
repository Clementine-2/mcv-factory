# Requirement Normalization Contract V0.1

## Purpose

Turn a natural-language project request into a conservative Project Blueprint V0.1 plus provenance metadata without inventing unsupported long-term project facts.

## Trust boundary

The normalizer MUST prefer omission or `unresolved` over invented completeness.

Source classes remain:

- `EXPLICIT`: directly stated by the user/request.
- `INFERRED`: a narrow semantic normalization of explicit wording, with an assumption record.
- `DETECTED`: reserved for future repository/environment evidence. The text-only P1 normalizer does not emit it.
- `DEFAULT`: reserved for later engineering defaults. The text-only P1 normalizer does not emit it.

## What the P1 reference normalizer may extract

Only high-signal project facts:

- project purpose (the normalized request text itself)
- work-product surface
- explicitly named technologies
- explicitly named target environments/platforms
- explicit lifecycle hints
- explicit scale hints
- explicit hard constraints
- explicitly named quality attributes

## What it must not infer

It must not infer or inject:

- Harness, Runner, Spec Kit, Copier, AionUI, Codex, Claude, or other Provider choices
- agent topology
- test framework
- repository layout
- CI/CD provider
- cloud vendor
- architecture pattern
- database choice
- security/reliability requirements that were not stated
- long-lived/production status just because the project sounds serious

## Minimal-question rule

A question is emitted only when a missing fact materially prevents choosing a safe/basic project surface.

P1 examples:

- Generic `app/application` with no surface -> ask web/mobile/desktop/etc.
- Mobile app with no iOS/Android target -> ask target platform.
- No recognizable work product -> ask what deliverable is intended.

Missing technology, lifecycle, scope, or quality requirements do not automatically trigger questions.

## Reserved unresolved placeholders

The P1 normalizer may temporarily use:

- `work_products[].kind: application`
- `work_products[].kind: unspecified`

only when the metadata marks the relevant path `resolution_required: true`. Such results are `NEEDS_RESOLUTION` and must not enter project materialization unchanged.

## Reference implementation vs production semantic extraction

`src/project_factory/normalizer.py` is a deterministic conservative baseline, not the final natural-language intelligence layer. Its purpose is to establish an executable trust contract and regression oracle.

A future LLM/harness-backed semantic adapter MAY produce richer extraction, but it must still satisfy this contract, preserve provenance, pass the same validator, and must not silently convert unsupported guesses into `EXPLICIT` facts.
