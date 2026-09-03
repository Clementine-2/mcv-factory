# P8 Closeout — Generated Project Upgrade & Migration

P8 implements a dry-run-first migration lifecycle for existing generated projects.

## Verified properties

- DryRun performs no project writes.
- Apply requires exact plan SHA confirmation.
- Managed-file conflicts block rather than overwrite.
- Blueprint provenance drift blocks.
- Business/source changes do not block overlay migration and are not rewritten.
- Exact locked Provider/version is required for verification.
- Rollback point is created before overlay writes.
- Rollback refuses to overwrite post-upgrade edits.
- Generation Project Manifest is preserved byte-for-byte.
- Factory Overlay Manifest verifies only the Factory-owned overlay.
- P7 -> P8 migrations pass for Python CLI, Python library, Node library, and browser extension Golden Projects.
- Browser runtime limitations remain unverified after migration.

See `evidence/P8_UPGRADE_MATRIX.json` for the real four-project migration matrix.

## Final baseline

- Factory 0.9.0
- 138/138 automated tests PASS before checkpoint freeze
- Four-project P7 -> P8 migration matrix PASS
- Four-project P8 Golden Matrix PASS within evidence-scoped statuses
- wheel outside-source upgrade plan/apply/rollback PASS
