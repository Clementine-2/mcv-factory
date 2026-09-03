# P4 Closeout — Verification Spine

## Status

P4 is complete, pending only checkpoint clean-restore evidence at packaging time.

## Implemented

- Independent `verification.py` Spine separated from scaffold recipes.
- Trusted verification suites selected by profile id; Registry cannot inject arbitrary shell commands.
- Command gates with return-code and output assertions.
- Artifact gates with actual path discovery and SHA256 evidence.
- Claim-to-gate evidence links.
- Claim statuses: VERIFIED / PARTIALLY_VERIFIED / UNVERIFIED / FAILED.
- Overall report statuses: VERIFIED / PARTIALLY_VERIFIED / FAILED.
- Required-gate failures block generation/restore verification.
- Browser runtime claims explicitly remain UNVERIFIED when browsers are not launched.
- Project Lock stores verification suite and claim summary.
- README/AGENTS wording no longer globally claims verification beyond evidence scope.
- Architecture guards prevent verification logic from drifting back into scaffold recipes or concrete gate ids into Factory Core.

## Bottom-layer evidence before checkpoint packaging

- 65/65 automated tests pass.
- Four Golden Projects regenerate and restore-verify.
- Python CLI: 3 VERIFIED material claims, 0 unverified.
- Python Library: 3 VERIFIED material claims, 0 unverified.
- Node Library: 3 VERIFIED material claims, 0 unverified.
- Browser Extension: 3 VERIFIED local claims + 2 UNVERIFIED real-browser claims => PARTIALLY_VERIFIED.
- Intentional failed required gate is recorded as EXECUTED/FAILED and blocks required-gate success.
- All generated Provider locks still record `upstream_source_modified=false`.
- No `.venv`, `node_modules`, `dist`, `.git`, `.tgz`, `.pyc` leakage in packaged Golden project roots.
- No P4 temporary absolute-path leakage found in generated project contents.
- Factory wheel 0.5.0 builds locally via `pip wheel --no-deps --no-build-isolation`.

## Explicitly not verified / not implemented

- Real Chrome runtime compatibility.
- Real Firefox runtime compatibility.
- Public PyPI or npm publication/install roundtrip.
- Production LLM semantic normalization.
- Real Formula/Policy decision engine beyond bootstrap formula.
- Codex/Claude Harness compatibility.
- Spec Kit integration.
- Upstream automated compatibility qualification.
- Generated-project upgrade/migration.
- Extension ecosystem packaging.
- AionUI/ACP integration.
- Long-running Runner integration.

## Architecture verdict

P0-P4 remain on the intended Project Factory path. One P3 responsibility drift (scaffolding + verification in the same adapter module) was corrected in P4.
