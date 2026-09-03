# Forward Roadmap after P10

Completed: P0-P10.

## P11 — Long Runtime

Goal: provide optional long-running execution as a Capability/Provider boundary without making the Interactive Host or Factory Core own the scheduler.

Required topology:

`OS/service -> Runner Provider -> Harness CLI -> Generated Project`

Interactive Host remains a peer path:

`Interactive Host -> Harness -> Generated Project`

P11 should first audit the previous AgentRunner contract against mature local-first orchestrators (Dagu remains a leading candidate) and keep adapters thin. No GUI coupling, no "Agent session must live for 8 hours" assumption, no automatic destructive retries.

## P12 — Productization & Dogfood Hardening

Bootstrap/doctor/first-run UX, real-project dogfood, release gates, recovery UX, packaging, documentation and final portable distribution.

## P∞

Core stability with continued Profiles/Formulas/Skills/Providers/Extensions/Golden Projects rather than continued Core reinvention.
