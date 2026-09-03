# P12 Closeout — Productization & Dogfood Hardening

## Stage objective

Turn the P0-P11 engineering kernel into a daily-usable local product surface without creating a new GUI, package manager, Harness, Runner runtime, or network crawler.

## Implemented product surface

- `project-factory --version`
- `project-factory doctor [--deep]`
- `project-factory bootstrap [--deep]`
- checkpoint recovery: `inspect -> plan (DryRun) -> exact plan hash -> restore to NEW directory`
- resumable eight-gate release gate
- local-install release bundle with wheel + exact Python dependency pins + checksums
- bounded compatibility refresh that does not mutate the stable Registry
- small and medium real-project dogfood

## Bottom-level evidence before checkpoint freeze

- P12 release gate: 8/8 PASS
- automated tests inside release gate: 209/209 PASS
- deep doctor: READY_WITH_WARNINGS
- compatibility refresh: PASS; stable Registry hashes unchanged
- standard Golden Matrix: 4/4 generation/restore; Python/Node VERIFIED, browser PARTIALLY_VERIFIED
- default Golden projects: Runner NOT_CONFIGURED
- P11 -> P12 generated-project upgrade: 4/4 PASS; business source preserved; first case exact rollback
- real product dogfood: small Python CLI + medium Node library PASS with native tests/builds
- Factory 0.13.0 wheel smoke outside source tree: PASS
- local release bundle CRC/checksums: PASS
- real P11 final checkpoint restored using P12 checkpoint UX: manifest 620/620 PASS

## External runtime truth boundary

The build environment does not contain Dagu, Codex, or Claude CLI. The release gate therefore records the live unattended Runner gate as `UNVERIFIED_ENVIRONMENT_UNAVAILABLE`.

No test double, generated DAG, successful `start` command, or static upstream contract is promoted to a live-runtime success claim.

## Distribution boundary

The local release bundle is **not** a fully offline dependency mirror. It includes the Project Factory wheel and pinned requirements, but not third-party dependency wheels. Standalone offline dependency resolution remains UNVERIFIED.

## Completion rule

P12 may be marked COMPLETE only after:

1. a candidate checkpoint is frozen;
2. that candidate is restored to a fresh directory and all P12 release gates are rerun from the restored tree;
3. final metadata is frozen into an exact final ZIP;
4. the exact final ZIP itself passes manifest + P12 release-gate recovery from another fresh directory.

The final exact-ZIP restore evidence is intentionally stored outside the ZIP so validating the final package cannot mutate the package being validated.

## Candidate clean-restore result

The frozen candidate checkpoint passed a complete fresh-directory restore: 758/758 manifest entries, 209/209 tests, deep doctor, compatibility refresh, standard Golden Matrix, Runner Matrix, controlled fake-Dagu Adapter lab, P11->P12 upgrade matrix, two-project product dogfood, Factory wheel smoke, local release verification, and checkpoint self-restore.

The only remaining release action after this text is frozen is exact-final-ZIP validation. That evidence is intentionally external.
