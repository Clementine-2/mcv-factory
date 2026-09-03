# P7 Retrospective Architecture Audit

## Verdict

ON COURSE.

P7 introduced a compatibility subsystem without moving network discovery or update mutation into Factory Core.

## Verified non-drift

- `factory.py` does not crawl release pages.
- dynamic `observed_latest` data is not stored in Registry package data.
- generation uses only explicit `SUPPORTED` Provider versions.
- a merely TESTED version cannot be used automatically.
- `TESTED -> SUPPORTED` is non-automatic.
- upstream version discovery does not modify existing generated projects.
- uv/npm upstream source remains unmodified.
- Spec Kit/Codex/Claude contract support remains separate from live runtime support.

## Drift found and corrected

P6 conflated `tested_versions` with versions permitted for normal generation. P7 split the concepts by adding `supported_versions` and changed normal Provider resolution to require support as well as test history.

This closes a future failure mode where an experimental compatibility trial could accidentally become production policy.

## Current yellow lights

1. Candidate artifact acquisition is not yet a portable/offline subsystem. P7 intentionally leaves unavailable upstream candidates PENDING rather than downloading from inside Core.
2. A future Compatibility Lab runner may need artifact cache/signature/checksum handling. That must remain outside Factory Core.
3. npm has multiple maintained release lines and runtime-engine constraints; the Lab must keep runtime compatibility explicit rather than treating a single numeric "latest" as universally appropriate.
4. Live Codex/Claude/Spec Kit runtime compatibility remains environment-dependent and unverified here.

## No-go drift for P8

P8 must not turn project migration into implicit Factory upgrade. Existing projects require explicit DryRun, diff, checkpoint, apply, verify and rollback semantics.
