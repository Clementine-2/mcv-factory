# P6 Retrospective Architecture Audit

## Verdict

ON COURSE. P6 did not turn Project Factory into a coding-agent harness.

## Evidence

- `factory.py` contains no literal Codex, Claude, Spec Kit, AGENTS.md, or CLAUDE.md product identifiers.
- Product-specific context paths live in `registry_data/harnesses.yaml` and `harness.py`.
- Spec Kit command construction lives in trusted `process.py`, not registry command strings and not Factory Core.
- Upstream source modification remains declared false for uv, npm, and Spec Kit adapter metadata.
- Generated Blueprint remains provider/harness neutral.
- Harness runtime truth is not promoted from static context parity to VERIFIED.

## Drift found and corrected

1. Plan-only process metadata originally called target harnesses `installed_harnesses`. This was corrected to `target_harnesses`; only execution evidence may claim installed integrations.
2. Project instructions were previously owned directly by root `AGENTS.md`. P6 introduced `.project/contract/agent-contract.md` as the canonical source and makes each harness file a byte-identical adapter materialization.
3. The Factory core briefly mentioned product-specific context filenames in README rendering. That wording was removed; product IDs remain outside Core.

## Size watch

Current Python source total: about 3,600 LOC.

Largest files observed at P6 closeout:

- `factory.py`: about 682 LOC
- `normalizer.py`: about 530 LOC
- `process.py`: about 360 LOC
- `verification.py`: about 337 LOC
- `registry.py`: about 335 LOC

Yellow light: P7 must not add upstream polling/version logic directly into `factory.py`. Compatibility-lab logic should be a separate subsystem.

## Explicit non-claims

P6 does not prove a real Codex or Claude Code session consumed the generated context correctly. Their executables are unavailable in the build environment. It also does not prove a real Spec Kit v1.0.1 installation because the CLI is unavailable and the environment cannot resolve PyPI. These remain runtime-unverified, not hidden failures.
