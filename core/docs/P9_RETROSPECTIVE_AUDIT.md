# P9 Retrospective Audit

## Verdict

ON COURSE.

P9 reduced the main post-P8 drift risk: new Profile/Policy/Formula/Provider/Migration capability no longer has to accumulate as direct Core edits. Core remains the composition and safety boundary; extension content stays namespaced and explicit.

## Checks against frozen architecture

- Harness ownership stolen by Factory: no.
- Runner ownership stolen by Factory: no.
- Extension package installation owned by Factory: no.
- Declarative arbitrary command execution: blocked.
- Trusted code loaded without explicit trust: blocked.
- Extension ids leaking into Factory Core: architecture guard added.
- Extension migration allowed into business source: blocked.
- Unregister deletes extension source/package: no.
- Same-version trusted code replacement accepted silently: blocked by bounded distribution fingerprint.
- Project Lock loses provenance: no; extension receipts are durable.
- Existing projects auto-install newly enabled extensions: blocked.
- Extension removal automatically mutates generated projects: no.
- Whole-disk hashing introduced: no.

## Evidence-driven corrections made during P9

1. Current P9 projects initially looked perpetually upgradeable because extension-aware rendering changed metadata even when Core was current. Upgrade now separates Core migration from actual extension migration and permits a true no-op.
2. Agent Contract initially did not expose materialized extension resources. Contract generation now lists scoped extension artifacts.
3. Version/id pinning alone was insufficient for trusted code. P9 now fingerprints stable content from the explicitly enabled distribution and blocks same-version content drift. A late audit found that pip-generated `direct_url.json`/`RECORD`/bytecode made the first fingerprint too environment-sensitive; those volatile installer/runtime files are now excluded, and equivalent installs from different wheel paths produce the same fingerprint.

## Size watch

Project Factory Python Core is approximately 5.8k lines at P9 closeout. This remains small enough for direct audit, but P10 and P11 must not add Host or Runner internals to Core. Host/Runner integration must remain adapter/provider boundaries.

## Deferred risks

- Trusted-code extensions are arbitrary Python trust; no sandbox or signature guarantee exists.
- No marketplace/catalog/reputation model exists.
- Extension dependency graphs are intentionally absent.
- Public third-party extension compatibility has not been validated; P9 validates the extension mechanism using bounded fixtures and a real local wheel.
- Real Codex/Claude/Spec Kit runtime remains environment-dependent and retains prior evidence status.
