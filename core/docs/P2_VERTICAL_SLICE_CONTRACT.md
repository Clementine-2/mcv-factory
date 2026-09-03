# P2 Minimal Vertical Slice Contract

## Goal

Prove one complete, deterministic path from a natural-language requirement to a verified, extractable native project ZIP without turning the Factory into a coding agent or harness.

## Supported P2 slice

- Work product: CLI
- Required technology: Python
- Materialization: minimal
- Scaffolding capability provider: `uv` through its public CLI
- Agent topology decision: one main agent
- Runner: not required
- Reviewer: not required for bootstrap
- Verification: CLI smoke, stdlib unit test, native package build, generated-project manifest verification, clean extraction re-test

## Boundaries

The Factory MAY generate a functional scaffold and bootstrap smoke behavior. It MUST NOT implement the user's domain-specific feature. That remains work for the coding agent after project generation.

The Blueprint MUST NOT contain `uv`, Harness, Runner, Spec Kit, Copier, Codex, Claude, or other provider selections. Provider identity belongs in generation resolution and Project Lock.

P2 MUST NOT auto-install missing providers. Missing `uv` is a visible blocking error.

## P2 exit gate

P2 is complete only if all of the following have bottom-level evidence:

1. The P1 test suite still passes.
2. The new P2 Factory tests pass.
3. A natural-language Python CLI requirement produces a project ZIP.
4. The project ZIP can be extracted into a clean directory.
5. The extracted project manifest verifies.
6. The extracted project CLI runs.
7. The extracted project unit tests pass.
8. The extracted project builds a wheel and source distribution.
9. No upstream source is vendored or modified.
10. The complete Factory P2 checkpoint itself can be extracted and all Factory tests rerun successfully.
