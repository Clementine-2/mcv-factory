# Forward Roadmap After P7

Completed finite stages:

- P0 Architecture Contract
- P1 Blueprint Kernel
- P2 Minimal Vertical Slice
- P3 Profiles & Scaffolding
- P4 Verification Spine
- P5 Semantic Intake & Decision Kernel
- P6 Harness Compatibility & Process Integration
- P7 Upstream Compatibility Lab

Next finite stage:

## P8 — Generated Project Upgrade & Migration

Objective:

Allow an existing generated project to compare its Project Lock and Factory overlay against a newer Factory version without silently changing user code.

Required sequence:

`Analyze -> DryRun -> Proposed Diff -> Risk Report -> Recovery Point -> Apply -> Verify -> New Lock`

P8 must preserve the P0 rule that Factory lifecycle and Generated Project lifecycle are separate.

P8 must NOT simultaneously start:

- P9 Extension Ecosystem;
- P10 Interactive Host/AionUI compatibility;
- P11 Long Runtime/Runner;
- P12 Productization.
