# P5 Closeout — Semantic Intake & Decision Kernel

Status: RELEASE CANDIDATE; final checkpoint clean-restore result is recorded in the external restore-evidence sidecar.

## Delivered

- guarded Semantic Adapter interface;
- deterministic baseline adapter retained as fallback/regression oracle;
- external semantic support/provenance contract for future LLM adapters;
- secret redaction at semantic persistence boundary;
- semantic intake receipt in Project Lock;
- explicit Intent and Repository State models;
- Formula Registry and trusted Formula Adapter layer;
- Policy Registry and Policy enforcement layer;
- baseline engineering Formula;
- safe-default Policy;
- Decision Trace and context persistence;
- `intake` CLI;
- `decide` CLI;
- fail-closed generation when Decision cannot be honored;
- refreshed four-project Golden Matrix;
- P0-P4 regression coverage retained.

## Verified before final checkpoint packaging

- 88 automated tests PASS;
- four Golden projects regenerated and clean-restored;
- Python CLI: VERIFIED material claims;
- Python Library: VERIFIED material claims;
- Node Library: VERIFIED material claims;
- Browser Extension: local material claims VERIFIED, real Chrome/Firefox runtime claims UNVERIFIED, overall PARTIALLY_VERIFIED;
- semantic external-adapter adversarial tests reject unsupported EXPLICIT/DETECTED claims;
- structured Provider leakage remains invalid Blueprint;
- unsupported Decision materialization blocks before output;
- upstream source modification remains false for tested scaffold Providers.

## Explicitly not implemented

- production OpenAI/Claude/other LLM semantic provider;
- Codex/Claude Harness compatibility;
- Spec Kit process integration;
- strict/elevated verification suite materialization;
- reviewer execution;
- multi-Agent execution;
- Runner/Dagu;
- existing-project upgrade;
- extension installation ecosystem.

## Exit

The final P5 completion claim is valid only together with a successful clean-restore run of the checkpoint ZIP. The release procedure must verify the manifest, re-run all tests, restore-verify all four Golden projects, and rebuild/smoke the Factory wheel. The result is stored outside the ZIP as `P5_COMPLETE_RESTORE_TEST_EVIDENCE.txt` so the package itself does not need to be mutated after verification.

Next finite stage: **P6 Harness Compatibility & Process Integration**.
