# P9 Closeout

Stage: P9 Extension Ecosystem
Factory: 0.10.0
Extension API: 1
Lock schema: 0.7

## Delivered

- versioned Extension Manifest schema;
- versioned Extension Set schema;
- DryRun-first add/enable/disable/remove registration lifecycle;
- declarative extensions with namespaced Registry contributions and scoped artifacts;
- trusted-code extensions discovered through PyPA entry points;
- explicit trust gate before code loading;
- typed Formula/Recipe/Verification/Migration registration;
- bounded stable-content trusted-distribution fingerprint in Project Lock;
- same-version trusted-code drift detection;
- extension-aware Registry, Decision, scaffolding, Verification, restore and upgrade paths;
- extension-scoped Migration hooks using the existing P8 rollback discipline;
- extension receipts and artifact hashes in generated projects;
- CLI inspect/plan/apply/list/doctor surfaces;
- actual local trusted-extension wheel smoke without global installation.

## Verification baseline before checkpoint restore

- 162/162 automated tests PASS;
- four core Golden Projects regenerated successfully;
- P8->P9 four-project migration matrix PASS;
- declarative extension Golden VERIFIED;
- trusted-code extension Golden VERIFIED;
- trusted extension scoped migration and rollback PASS;
- Factory wheel outside-source extension lifecycle + generation + restore PASS;
- real local PyPA trusted extension wheel discovery/fingerprint/generation/restore PASS; equivalent installs from different local wheel paths produce the same stable fingerprint.

## Truth boundaries

- P9 proves the extension contract and local trusted wheel mechanism, not a public ecosystem.
- Trusted-code means full trust in the installed Python extension distribution; it is not sandboxed.
- Factory does not install, uninstall, update or delete extension packages.
- `remove` is registration removal only.
- No extension marketplace or publisher trust system exists.
- Real third-party extension interoperability remains UNVERIFIED.

## Candidate checkpoint restore

The candidate checkpoint completed manifest verification, 162/162 tests, base Golden regeneration, P8->P9 migration, extension Golden/migration tests, Factory wheel outside-source smoke and a real local trusted-extension wheel entry-point smoke. The final delivered ZIP is separately re-verified and accompanied by external restore evidence.

## Stable fingerprint correction and restore

A late evidence review showed that installer-generated `direct_url.json`, rewritten `RECORD`, `INSTALLER`, `REQUESTED`, and bytecode made the first trusted-distribution fingerprint environment-sensitive. P9 now fingerprints only stable package/publisher content. An equivalent-install smoke from two different local wheel paths produces the same fingerprint. The corrected candidate then passed the complete clean-restore gate.
