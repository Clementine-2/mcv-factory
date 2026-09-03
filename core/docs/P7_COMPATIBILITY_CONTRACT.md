# P7 Upstream Compatibility Lab Contract

## Purpose

P7 separates fast-changing upstream discovery from the stable Project Factory Registry.

Dynamic upstream observations are evidence inputs. They do not automatically change what the Factory is allowed to use.

## State language

For runtime providers:

- `PENDING`: an upstream candidate is known but cannot yet be executed in the lab.
- `CANDIDATE_READY`: the exact candidate artifact/runtime is locally available and can enter lab execution.
- `TESTED`: every required compatibility check passed, but the version has not been admitted to production generation.
- `SUPPORTED`: the version is both tested and explicitly admitted for project generation.
- `REJECTED`: a required compatibility condition failed.

For Harness/Process contracts:

- `CONTRACT_SUPPORTED`: the public interface/contract is pinned and supported by the adapter, but live runtime behavior is still unverified.

Contract support and runtime support are deliberately separate.

## Non-automatic promotion

A new version may only move:

`PENDING -> CANDIDATE_READY -> TESTED -> SUPPORTED`

when evidence exists for each transition.

`TESTED -> SUPPORTED` produces a promotion proposal only. P7 does not mutate the supported Registry automatically.

## Stable support state

`src/project_factory/registry_data/compatibility.yaml` stores durable tested/supported state.

It MUST NOT store transient fields such as:

- observed latest version;
- release publication timestamp;
- network query response;
- "latest" aliases.

## Dynamic observation state

`compatibility/observations/*.yaml` stores dated upstream observations with source URLs.

These files are historical evidence snapshots and may become stale. They do not themselves authorize generation.

## Provider generation gate

Project generation requires the installed Provider version to be both:

1. listed in `tested_versions`;
2. listed in `supported_versions`.

A version that was tested experimentally but not explicitly supported MUST fail closed during normal generation.

## Lab isolation

The compatibility subsystem MUST remain separable from `factory.py`.

The compatibility core MUST NOT become a network crawler or auto-updater. Network/source discovery belongs outside the deterministic Factory kernel; its normalized observation is passed into the lab as evidence.

## Provider lab checks

Current P7 provider adapters use the same trusted scaffold + Verification Spine as generated projects.

### uv

Required checks:

- version probe;
- Python CLI Golden scaffold + verification;
- Python Library Golden scaffold + verification;
- upstream source diff = 0.

### npm

Required checks:

- version probe;
- Node Library Golden scaffold + verification;
- Browser Extension Golden scaffold + verification;
- upstream source diff = 0.

## Runtime eligibility before execution

A candidate may be rejected before artifact execution when an upstream-declared runtime requirement is provably incompatible with the observed environment.

This is not equivalent to an upstream defect. It means only that the candidate is incompatible with the current lab environment.

## Failure taxonomy

P7 distinguishes at least:

- `RUNTIME_INCOMPATIBLE` — candidate's declared runtime contract excludes the lab runtime;
- `CANDIDATE_ARTIFACT_UNAVAILABLE` — candidate is known but not locally executable in the lab;
- lab check failure — exact executable was tested and a required gate failed;
- `RUNTIME_UNVERIFIED` — contract is supported but real executable/runtime was not exercised.

## Project Lock

P7-generated projects record:

- Provider ID/version;
- `compatibility_state = SUPPORTED`;
- compatibility policy requiring `SUPPORTED` for generation;
- `automatic_promotion = false`.

Thus a Project Lock can show that a Provider version was admitted, rather than merely observed.
