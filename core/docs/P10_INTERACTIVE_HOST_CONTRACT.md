# P10 Interactive Host Contract

Stage: P10 Interactive Host Compatibility
Factory: 0.11.0
Lock schema: 0.8
Host contract schema: 0.1

## Role

An Interactive Host is a replaceable user-interface entry point over a generated native project and existing Agent Harnesses. A Host is not a Harness, Runner, Verification authority, Project Factory Extension manager, or Project Lock owner.

## P10 AionUI adapter

P10 ships one opt-in Host adapter: `aionui`.

It is deliberately **plan-only**. Project Factory does not install, launch, upgrade, configure, authenticate, or mutate AionUI. It creates only:

- `.project/host/aionui.json`
- `.project/host/README.md`
- `.project/evidence/host-compatibility.json`
- corresponding Project Lock provenance

The generated plan points AionUI at the project workspace and names compatible already-materialized Harness adapters (`codex`, `claude`). It does not install bridge software or create a Host-private runtime directory.

## Ownership invariants

Every registered Host must explicitly declare these as `false`:

- `owns_extensions`
- `owns_verification`
- `owns_runner`
- `owns_harness_runtime`
- `owns_project_lock`

Registry loading fails closed if a Host claims one of those surfaces.

## Verification semantics

P10 distinguishes:

- Host plan/materialization integrity: can be VERIFIED;
- live Interactive Host runtime: remains UNVERIFIED unless an actual Host session and known task are executed with evidence.

Therefore an AionUI-enabled generated project can still be `VERIFIED` for its project gates while `host_integration.status` is `PARTIALLY_VERIFIED`.

## No framework tax

Hosts are opt-in. If no Host is selected, `.project/host/` and Host evidence are absent and `project.lock.json.host_integration` is null.

## Restore/upgrade

Host plan files are Factory-managed overlay files when configured. Their hashes enter `managed_files` and the Factory Overlay Manifest. Tampering blocks Host verification and current-upgrade analysis. P9 projects upgrade to P10 without silently adding AionUI.
