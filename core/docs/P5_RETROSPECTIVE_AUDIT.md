# P5 Retrospective Architecture Audit

## Verdict

**ON COURSE.** P5 adds decision intelligence without introducing a Harness.

## Checks

### Harness drift

PASS.

No model loop, session manager, context manager, generic tool dispatcher, multi-Agent scheduler, or model runtime was added.

### Normalizer drift

IMPROVED.

The legacy deterministic Normalizer remains as a conservative supported baseline. New semantic intelligence now has a replaceable adapter boundary instead of requiring continued regex growth.

### Formula drift

IMPROVED.

Formula implementation was moved out of Decision Core into `formulas.py`; declarations live in Registry data. New formulas no longer belong in `factory.py`.

### Policy precedence

PASS.

Long-running autonomy can cause a Formula to request a Runner, but `safe-defaults` suppresses it because P5 has no verified Runner capability.

### Decorative decision risk

FOUND AND FIXED.

Early P5 could record a strict/reviewer Decision while continuing through baseline generation. P5 closeout changed this to fail closed: the materializer must prove it can honor the Decision before writing project output.

### Upstream preservation

PASS.

Golden projects continue to use public `uv`/`npm` interfaces with `upstream_source_modified=false`.

### Framework tax

PASS for current four Golden Profiles.

No new project directories or runtime dependencies were imposed merely to host P5 semantics/decisions; the additional provenance lives in existing `.project`/Lock surfaces.

## Yellow lights

1. `normalizer.py` remains a legacy deterministic implementation and must not become an ever-growing NLP engine.
2. P5 defines but does not yet ship a production external/LLM Semantic Adapter.
3. Formula adapters are still trusted in-process code; later Extension work must make third-party formulas installable without turning Registry YAML into arbitrary code execution.
4. Elevated/strict verification decisions currently block new-project generation rather than being materialized. This is correct for P5 but becomes a capability gap for later phases.
5. `factory.py` remains the largest orchestration module and should not absorb Harness/process/upstream lifecycle logic in later phases.
