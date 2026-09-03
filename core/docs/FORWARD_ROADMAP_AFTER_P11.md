# Forward Roadmap after P11

Completed after final restore gate: P0-P11.

## P12 — Productization & Dogfood Hardening

Goal: make the Factory practical to start, inspect, repair, package and use on real projects without expanding Core abstractions.

Primary work:

- bootstrap/doctor/first-run UX;
- distribution and local install path;
- recovery UX and checkpoint discoverability;
- real-project dogfood across small/medium project families;
- release gate automation and evidence summaries;
- documentation cleanup and entrypoint simplification;
- bounded compatibility refresh workflow for upstream Providers/Harnesses/Hosts;
- live Runner dogfood when a verified Dagu + Harness environment is available.

P12 must not turn into GUI-first development or reopen multiple infrastructure lines. Productization should expose the existing spine rather than create a new orchestration layer.

## P∞

Stabilize Core. Future growth should prefer Profiles, Formulas, Skills, Policies, Providers, Adapters, Extensions and Golden Projects over additional Core concepts.
