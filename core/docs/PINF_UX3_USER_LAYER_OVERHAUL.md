# P∞ UX3 User Layer Overhaul

Date: 2026-08-30
Factory: 0.14.1 / P∞
Studio: UX3.0

## Scope

UX3 is a user-layer overhaul, not a new Core phase. It keeps the P∞ architecture and exposes mature Core capabilities through a product-oriented Windows Studio.

## Product shell

The Windows Studio uses ttkbootstrap 2.2.2 as the GUI/theme toolkit rather than continuing to hand-style raw Tk widgets. The product shell is split into:

1. Dashboard / capability status
2. New Project / Requirements Workbench
3. Project History
4. Check & Verify
5. Compatibility Lab
6. Network & Downloads
7. Advanced Integrations
8. Tasks & Logs
9. Settings & Customization

The default theme is `nord-light`; users may switch supported themes. AI assistance is OFF by default.

## Natural language to project package

The authoritative flow is:

```text
Natural-language requirement
-> deterministic local parsing
-> editable requirement matrix
-> optional AI advisory enrichment / clarification
-> user confirmation
-> Blueprint schema + policy + registry gates
-> Profile / Formula / Provider selection
-> generate
-> verify
-> project directory + verified ZIP
```

The requirement matrix covers purpose, work products, required/preferred/prohibited technology, targets, hard constraints, quality attributes, lifecycle, scope, profile preview, provenance, and open questions.

AI is not the authority. It cannot bypass deterministic gates, and the Factory remains usable with AI disabled, offline, or unavailable.

## AI safety boundary

A real cross-layer defect was fixed in 0.14.1: external semantic adapters previously could receive raw requirement text before output-side secret redaction. External adapters now receive redacted requirement text. The Studio stores only the API-key environment-variable name; a session secret is not persisted in settings.

`UserConfirmedSemanticAdapter` represents the user's confirmed structured matrix and still passes schema/readiness validation.

## Performance

- In-process Core calls are used for status, generation, check, and verification where appropriate.
- Status is cached for 60 seconds and can be manually refreshed.
- Long work runs on background threads.
- There is no periodic subprocess polling loop.
- External tools/providers remain subprocesses where isolation is appropriate.

## Network defaults

Based on real Windows predecessor evidence, UX3 defaults to:

- source: Tsinghua TUNA
- connection: forced direct / ignore inherited proxy

Users can choose official PyPI, current system/proxy configuration, custom proxy, and other supported connection strategies. Third-party mirrors are not silently selected behind the user's back.

## Compatibility candidates

Observed system versions such as uv 0.11.28 and npm 11.16.0 are treated as candidates. Compatibility Lab can run temporary Golden verification and emit evidence. It does not auto-promote a version into the Registry.

## Verification status

Verified:
- Core 0.14.1 final regression: 232/232 PASS.
- Final wheel built and package-outside-source smoke passed.
- UX3 Studio logic self-test passed under the build-only GUI shim.
- Bootstrap static self-test passed.
- UX3 Windows bundle exact ZIP CRC and checksums passed.

Not yet verified:
- actual ttkbootstrap 2.2.2 rendered UX3 window on the user's target Windows machine.
- real DPI/theme/visual behavior on that target.

Therefore UX3 is a release candidate for real-user Windows UI testing, not a visually-final product claim.
