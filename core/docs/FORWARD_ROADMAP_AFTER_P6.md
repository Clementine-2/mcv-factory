# Forward Roadmap After P6

Current completed sequence:

P0 Architecture Contract -> P1 Blueprint Kernel -> P2 Vertical Slice -> P3 Profiles/Scaffolding -> P4 Verification Spine -> P5 Semantic/Decision Kernel -> P6 Harness/Process Contract.

## Next major stage: P7 Upstream Compatibility Lab

P7 should not add more product features. It should build the maintenance system that lets Project Factory consume upstream releases safely.

Core objectives:

1. Separate `latest`, `candidate`, `tested`, and `supported` versions.
2. Define provider/harness/process compatibility records with source, version, date, evidence, and limitations.
3. Run Golden Matrix tests against candidate upstream versions in isolation.
4. Never promote a version solely because it is newest.
5. Record failure without modifying existing generated projects.
6. Add a local/offline-compatible compatibility-test path where possible.
7. Include real Codex/Claude/Spec Kit runtime probes when those executables become available; until then retain runtime claims as UNVERIFIED.

## Later finite stages

- P8 Generated Project Upgrade & Migration
- P9 Extension Ecosystem
- P10 Interactive Host Compatibility
- P11 Long Runtime
- P12 Productization & Dogfood Hardening
- P-infinity: ongoing Profiles/Formulas/Skills/Providers without uncontrolled Core growth
