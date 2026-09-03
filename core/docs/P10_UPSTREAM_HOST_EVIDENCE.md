# P10 Upstream Host Evidence

Observed: 2026-08-30

## AionUI

Current public AionUI documentation describes Multi-Agent Mode as optional. It auto-detects external CLI agents already present on `PATH`, presents them through one Cowork UI, and connects supported external agents via ACP or an AionUI compatibility adapter. External agents retain their own model, authentication, tools, and behavior.

Contract source:
- https://github.com/iOfficeAI/AionUi/wiki/ACP-Setup
- wiki snapshot observed updated 2026-08-06

Observed latest GitHub release at P10 implementation time:
- AionUI v2.1.61
- published 2026-08-25
- https://github.com/iOfficeAI/AionUi/releases/tag/v2.1.61

This release observation is evidence, not a durable requirement in `hosts.yaml`. The Host Registry pins the interaction contract snapshot, not "latest".

## Runtime environment

The P10 execution environment did not expose AionUI, Codex, Claude Code, or Spec Kit CLI executables. Therefore no live AionUI GUI session was claimed.

## Architectural consequence

AionUI is treated as a peer Interactive Host. Project Factory does not route Runner ownership through AionUI and does not require AionUI for direct CLI Harness use.
