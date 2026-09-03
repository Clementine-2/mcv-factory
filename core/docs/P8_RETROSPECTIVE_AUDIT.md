# P8 Retrospective Architecture Audit

## Verdict

ON COURSE.

P8 adds lifecycle capability without moving update logic into Factory generation, Provider compatibility, or Harness internals.

## Drift caught and corrected

The first P8 implementation rewrote `PROJECT_MANIFEST.sha256` after migration. That would have re-baselined user-evolved source files and blurred Factory ownership. It was removed before closeout.

The final design leaves the generation manifest unchanged and introduces a Factory Overlay Manifest restricted to Factory-owned paths.

A second safety issue was also corrected: rollback initially restored preimages without proving that the post-upgrade files had not been edited since apply. P8 now requires a postimage receipt and fails closed on such changes.

A third issue was corrected: upgrade verification initially resolved the current preferred Provider. It now uses the exact Provider id/version stored in Project Lock and blocks Provider migration.

## Architecture guards

Automated tests assert:

- upgrade.py does not contain network discovery clients;
- upgrade targets do not include generic `src/` or `tests/` trees;
- no automatic-apply CLI flag exists;
- explicit plan confirmation is required.

## Remaining yellow lights

P8 supports the current overlay migration contract, not arbitrary future schema graph migration. A future extension ecosystem must provide migration registration without turning `upgrade.py` into a giant version switch.

Rollback bundles are local immediate-undo artifacts on the same storage domain. They are intentionally not called backups.
