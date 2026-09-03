# Architecture Baseline P0.1

## Mission

Project Factory converts software-development intent into a native project with suitable structure, engineering discipline, capability configuration, verification, recoverability, provenance, and compatibility with existing Agent Harnesses.

## Product boundary

Project Factory = Project Factory + Project Standard + Component Registry.

It is not an Agent Harness, IDE, generic workflow engine, generic Agent runtime, virtual software company, programming framework, or build system.

## Frozen invariants

1. Blueprint describes the project, not concrete tools.
2. Intent describes the current task and does not pollute long-term project identity.
3. Capability expresses the need; Provider expresses the current implementation.
4. Formula decides; it does not execute engineering work.
5. Project Standard unifies semantics, not business directory trees.
6. Verification produces Evidence; tests are one form of Verification.
7. Generated projects remain normal native projects and should be escapable from Factory metadata.
8. Simple projects must remain simple; complexity is progressive.
9. Upstream source is unmodified by default.
10. Factory, Harness, and Runner must not seize each other's control planes.
11. Completion status must correspond to real Evidence.
12. All current concrete upstream tools must remain replaceable in principle.

## Stable core language

- Intent
- Project Blueprint
- Formula
- Profile
- Policy
- Skill
- Capability
- Provider
- Adapter
- Verification Gate
- Evidence
- Checkpoint
- Registry
- Factory
- Generated Project
- Project Lock
- Upgrade Plan

## Upstream preservation rule

Customization order:

1. Configuration
2. Extension / Plugin
3. Adapter / Wrapper
4. Upstream Issue / PR
5. Minimal Patch
6. Fork

The target is upstream source diff approximately zero.

## Progressive materialization

Project Standard defines required semantics, not a fixed file tree. A tiny utility may contain only an agent instruction file, lock metadata, and source. Larger projects may materialize policies, skills, verification, and checkpoints in separate files/directories.

## Intent vs Blueprint

Execution decisions conceptually depend on:

`F(Project Blueprint, Current Intent, Repository State, Applicable Policies)`

Project scale is not task scale.

## Verification

Verification is any acceptance process that produces Evidence. Software tests, build results, runtime observations, reproducible notebook execution, artifact checks, and human review records can all be Verification.
