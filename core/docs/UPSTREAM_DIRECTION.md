# Upstream Direction — Architectural Context Only

This document preserves pre-P1 research direction so a lost conversation does not erase the intended ecosystem strategy. These are candidates/directions, not P1.2 runtime dependencies and must be re-verified before adoption.

## Core rule

Project Factory should assemble mature upstream capabilities rather than fork or reimplement them. Concrete products are replaceable Providers behind stable Capability boundaries.

## Current candidate map

- Process/specification composition: GitHub Spec Kit is the leading candidate upstream. Do not fork its core by default.
- Project templating/scaffolding lifecycle: Copier is a leading candidate for Factory-owned overlay templates; prefer native language/framework scaffolders where available.
- Long-running execution/process lifecycle: Dagu is a candidate external Runner Provider; do not merge its source into Factory. Old custom AgentRunner should be audited rather than assumed worth preserving.
- Interactive GUI host: AionUI should be treated as a peer entry point/host for coding harnesses, not as something a Runner must embed into.
- Coding harnesses: Codex, Claude Code, and future harnesses remain external execution environments. Factory must not implement their agent loops.

## Intended topology

Interactive path:

`Generated Project -> Codex/Claude/etc. directly or through a GUI host`

Long-running path:

`Runner Provider -> Harness CLI -> Generated Project`

The Runner and GUI host are peer entry paths. Avoid a topology where the Runner must deeply adapt itself into a GUI host.

## Dependency preservation

For upstream customization use, in order:

1. configuration
2. extension/plugin
3. adapter/wrapper
4. upstream issue/PR
5. minimal patch
6. fork

A provider that requires a very thick adapter in an early PoC should trigger provider/topology re-evaluation before custom infrastructure is expanded.

## Product naming

"Beer" is the user's nickname only. It is not the product name. "Project Factory" is a neutral working name until naming is handled separately.
