# P7 Closeout — Upstream Compatibility Lab

## Delivered

- durable compatibility Registry separate from dynamic upstream observations;
- explicit `tested_versions` vs `supported_versions` distinction;
- normal generation now requires Provider state `SUPPORTED`;
- generic candidate observation evaluator;
- normalized runtime-requirement evaluation;
- isolated local Provider lab using trusted Scaffold Recipes + P4 Verification Spine;
- non-automatic promotion proposal contract;
- CLI/status report path;
- current uv/npm supported versions revalidated by real local Golden checks;
- current upstream observation snapshot for uv/npm/Spec Kit/Harness contracts;
- wheel/package integration for compatibility module and compatibility Registry.

## Current compatibility facts

- uv 0.10.0: SUPPORTED and revalidated.
- uv 0.12.7: PENDING, exact candidate artifact unavailable in lab.
- npm 10.9.2: SUPPORTED and revalidated.
- npm 10.9.9: PENDING, runtime-compatible but exact candidate artifact unavailable.
- npm 12.0.2: REJECTED for current Node 22.16.0 runtime due upstream engine floor.
- Spec Kit 1.0.1: CONTRACT_SUPPORTED, runtime UNVERIFIED.
- Codex contract snapshot: CONTRACT_SUPPORTED, runtime UNVERIFIED.
- Claude contract snapshot: CONTRACT_SUPPORTED, runtime UNVERIFIED.

## Truth boundary

P7 did NOT claim to execute uv 0.12.7, npm 10.9.9, npm 12.0.2, Spec Kit, Codex, or Claude when their exact runtime/artifact was unavailable.

No new upstream version was promoted in P7.
