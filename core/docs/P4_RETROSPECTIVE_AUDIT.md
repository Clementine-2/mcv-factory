# P0-P4 Retrospective Architecture Audit

## Verdict

**ON COURSE, WITH ONE DRIFT CORRECTED IN P4.**

## What stayed aligned

1. Factory remains a project producer, not an Agent Harness.
2. No Agent loop, context manager, scheduler, Runner or multi-Agent control plane was introduced.
3. Blueprint remains Provider-neutral.
4. Native ecosystem scaffolders are used through public CLI interfaces.
5. Tested upstream source modification remains zero.
6. Generated projects remain normal native projects and can survive without Factory metadata for basic development.
7. Complexity is progressive: four project families use thin overlays instead of a universal business directory tree.
8. Claims increasingly require bottom-layer evidence instead of Agent self-report.

## Drift found and corrected

P3 `recipes.py` owned both scaffolding and verification behavior. Continued growth would have turned Recipe Adapter into a new mixed-responsibility framework.

P4 moved verification into an independent `verification.py` Spine and added architecture tests preventing the old ownership from returning.

## Watch items, not current failures

### Deterministic Normalizer size

`normalizer.py` is already a substantial module. It must remain a conservative baseline rather than evolve into a hand-built universal NLP engine. Rich semantic interpretation should later be an optional LLM adapter behind the same Blueprint contract.

### Factory Core size

`factory.py` remains an orchestration-heavy module. Future stages should avoid putting Harness, upgrade, Runner or plugin implementation directly inside it.

### Spec Kit has not yet been integrated

This is deliberate rather than accidental. P0-P4 established the Factory-owned IR, Registry and Evidence contracts first. Spec Kit should be evaluated as an upstream process/Harness integration component, not used to define Factory Core semantics.

### No public-provider lifecycle yet

The Registry knows tested versions, but automated upstream compatibility qualification is not implemented. That belongs to a later compatibility stage.

## Anti-reinvention check

Factory-owned code currently implements only areas intentionally identified as our differentiating control plane:

- Blueprint normalization/validation contract.
- Capability/Profile/Provider resolution.
- Evidence-first verification semantics.
- Thin project composition/provenance.

Scaffolding remains delegated to `uv` / `npm`. Harness, GUI, Runner and general workflow scheduling remain external.
