# Operations and Evidence

## Human readiness

`project-factory status` is the first user-facing readiness command. It is read-only. `--deep` performs a temporary end-to-end smoke without keeping product output.

`project-factory check PROJECT_DIR` is also read-only and does not execute runtime commands from the generated project.

## Doctor

`project-factory doctor` remains the detailed machine/diagnostic surface. It checks packaged schemas/registries, supported local Providers, optional external runtime presence and profile readiness. `--deep` generates and restore-verifies a temporary Python CLI without keeping product output.

## Compatibility refresh

`scripts/run_compatibility_refresh.py` consumes an explicit observation file plus local runtime probes. It has no network fetch code and verifies that stable Registry files have identical hashes before/after. Candidate discovery, testing and promotion remain separate lifecycle steps.

## Release gate

`scripts/run_release_gate.py` runs nine internal gates into an explicitly empty work directory and writes independent logs/evidence for each gate: tests, deep doctor, compatibility, Golden matrix, Runner matrix, source-stage upgrade/rollback matrix, product dogfood, wheel smoke, and the bounded brutal suite.

Each subprocess has a timeout. On timeout, the release gate terminates the process tree, records return code 124 and does not convert missing downstream gates into success. `--resume` only reuses explicit PASS evidence.

## Brutal suite

`scripts/run_brutal_suite.py` is temporary-destructive only. It uses isolated temporary/output directories and covers:

- malicious archive/path traversal and symlink cases;
- overwrite refusal and post-refusal integrity;
- same-output concurrency and different-output parallel generation;
- forced subprocess timeout including child-process termination;
- checkpoint plan/hash/repeat-restore failure paths;
- repeated read-only checks;
- bounded invalid-name/manifest-path fuzzing and oversized requirement rejection.

It never authorizes automatic deletion of persistent user business data.

## Live Runner truth boundary

Presence of Dagu/Codex/Claude is not task success. `dagu start` returning zero is not workflow completion. Real unattended dogfood must record runtime status and downstream Verification evidence separately.
