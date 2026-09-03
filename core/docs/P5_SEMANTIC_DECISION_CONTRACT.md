# P5 Semantic Intake & Decision Kernel Contract

Status: FROZEN FOR P5

## 1. Purpose

P5 separates two responsibilities that were previously only prototypes:

1. **Semantic Intake** turns natural-language project requirements into Blueprint + metadata while preserving uncertainty and provenance.
2. **Decision Kernel** turns Blueprint + current Intent + Repository State + Policy into an Execution Decision without executing project work.

Neither subsystem is an Agent Harness.

## 2. Semantic Adapter boundary

A Semantic Adapter may interpret user language, including a future LLM-backed implementation, but it may not bypass the Blueprint validator or provenance contract.

The default tested adapter is:

- `deterministic-baseline@0.2`
- trust class: `deterministic-baseline`

P5 also defines an `external-semantic` trust class for future LLM/semantic adapters.

### External semantic support contract

For an external semantic adapter:

- every provenance path must have one matching support record;
- `EXPLICIT` and `INFERRED` support must cite text actually present in the source requirement;
- `INFERRED` and `DEFAULT` support require a reason;
- a text-only adapter may not claim `DETECTED` repository facts;
- all output is secret-redacted before persistence;
- all Blueprint and metadata output still passes the deterministic P1 validator;
- Provider/Harness fields remain illegal Blueprint structure.

The Factory stores an intake receipt containing adapter identity, source requirement hash, guard result, redaction count, and external support records when present.

### Important limitation

P5 does **not** ship or claim a production LLM provider. It freezes the guarded interface that such a provider must satisfy. Harness/model-specific integration remains outside this stage.

## 3. Intent and Repository State

The Decision Kernel explicitly separates long-lived Project Blueprint from the current task context.

Current Intent contains:

- `kind`
- `change_scope`
- `risk`
- `autonomy`

Repository State currently contains:

- whether the project already exists;
- clean/dirty worktree observation when known;
- test-state observation when known.

The initial new-project Factory path uses a `bootstrap` Intent and non-existing Repository State.

## 4. Formula model

Formula definitions are registered declaratively in `registry_data/formulas.yaml`.

Formula implementation lives in a trusted Formula Adapter layer (`formulas.py`), not in Factory Core.

Current tested Formula:

- `baseline-engineering@0.1`
- adapter: `baseline-engineering-v1`

Formula output may decide:

- materialization depth;
- verification depth;
- reviewer requirement;
- runner requirement;
- checkpoint policy;
- isolation requirement;
- Agent topology and parallelism.

Formula code does not execute subprocesses or project operations.

## 5. Policy model

Policies are registered in `registry_data/policies.yaml` and applied after Formula output.

Current tested Policy:

- `safe-defaults@0.1`

Rules:

- `max_parallelism: 1`
- `allow_multi_agent: false`
- `allow_runner: false`
- `require_evidence: true`

This proves precedence: a Formula may request a long-running Runner, but the current safe Policy suppresses it until a later stage explicitly introduces and verifies that capability.

## 6. Decision trace

Every Decision records:

- Formula identity/version/adapter;
- Policy identity/version/rules;
- Intent;
- Repository State;
- final Execution Decision;
- human-readable Decision Trace.

This information is persisted in Project Lock and `.project/generation.json` for generated projects.

## 7. Fail-closed materialization

A Decision is not decorative metadata.

`generate_project()` refuses to materialize when the current P5 generator cannot honestly satisfy the Decision. Examples:

- elevated/strict verification requested but only baseline suite exists;
- independent reviewer required but no reviewer integration exists;
- standard materialization requested but selected Profile only supports minimal;
- non-bootstrap intent is sent to the new-project generator;
- existing-project isolation is required;
- unsupported Agent topology or Runner is required.

The block occurs before project files are materialized.

## 8. Stable boundaries

P5 preserves these P0 invariants:

- Semantic Adapter interprets; Validator judges structure/readiness.
- Formula decides; it does not execute.
- Policy constrains; lower-level logic cannot silently override it.
- Blueprint remains Provider/Harness-neutral.
- Factory does not implement LLM loops, Agent context, schedulers, or model runtimes.
- Unsupported capability is a visible block, not a silent downgrade.
