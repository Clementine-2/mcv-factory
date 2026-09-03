# Forward Roadmap after P5

## Completed

- P0 Architecture Contract
- P1 Blueprint Kernel
- P2 Minimal Vertical Slice
- P3 Profiles & Scaffolding
- P4 Verification Spine
- P5 Semantic Intake & Decision Kernel

## Next finite stages

### P6 Harness Compatibility & Process Integration

Validate the same generated project/contract through multiple existing Harnesses and determine how much process integration should be delegated to Spec Kit instead of implemented locally.

### P7 Upstream Compatibility Lab

Separate `latest`, `tested`, and `supported`; automate isolated compatibility evaluation of upstream versions against Golden Projects.

### P8 Existing Project Upgrade & Migration

Implement explicit Analyze → DryRun → Diff → Recovery Point → Apply → Verify → New Lock lifecycle.

### P9 Extension Ecosystem

Make Formula/Profile/Skill/Policy/Provider extensions installable without modifying Core or allowing arbitrary Registry-data code execution.

### P10 Interactive Host Compatibility

Validate GUI/ACP hosts as optional peer entry points, not Core dependencies.

### P11 Long Runtime

Evaluate mature Runner providers and retain only a thin lifecycle adapter/contract.

### P12 Productization & Dogfood Hardening

Bootstrap/doctor UX, robust packaging, real personal-project dogfood, release gates, and the final “requirement in → ready project package out” workflow.

### P∞ Continuous Evolution

New Profiles, Formulas, Skills, Providers, Golden Projects, and domain extensions without routine Core rewrites.
