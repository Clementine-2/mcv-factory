# P12 Productization Contract

P12 exposes the existing P0–P11 architecture as a practical local product surface. It does not introduce a new orchestration layer.

## Product commands

- `project-factory --version`: exact Factory version/stage.
- `project-factory bootstrap [--deep]`: first-run readiness and quickstart; creates no persistent Factory state.
- `project-factory doctor [--deep]`: read-only registry/schema/provider/runtime diagnosis. `--deep` uses a temporary project and removes it with the temporary workspace lifecycle.
- existing `generate`, `restore-verify`, `upgrade`, `extension`, `host`, `runner`, and compatibility commands remain the engineering spine.
- `project-factory checkpoint inspect|plan|restore`: recovery UX for checkpoint ZIPs.

## Recovery discipline

Checkpoint restore is always:

`inspect -> DryRun plan -> exact plan SHA256 -> new destination -> MANIFEST verification`.

It never merges into or overwrites an existing destination. Failed extraction is not auto-deleted, because the partial state is evidence and automatic deletion is outside the project safety policy.

## Distribution boundary

P12 ships a standard Python wheel with a `project-factory` console entry point and a local-install ZIP containing the wheel, exact dependency pins and install instructions.

The bundle is **not** an offline dependency mirror. Third-party dependency wheels are not included. A network/index or separately supplied dependency cache may still be required for a clean machine.

## Release gate

The P12 release gate composes existing evidence-producing tools rather than owning project correctness. Required internal gates are:

1. full automated tests;
2. deep doctor;
3. bounded compatibility refresh with no registry mutation;
4. four standard Golden Projects;
5. Runner plan/restore matrix;
6. P11 -> P12 upgrade/rollback matrix;
7. small + medium real-project dogfood;
8. wheel/console/recovery smoke outside the source tree.

A real Dagu + authenticated Codex/Claude unattended shift is an external-runtime gate. If those runtimes are absent, the release gate records `UNVERIFIED_ENVIRONMENT_UNAVAILABLE`; it never substitutes a fake runtime for live evidence.

## Non-goals

P12 does not add a GUI, plugin marketplace, package manager, network crawler, Harness runtime, Runner runtime, or automatic upgrade daemon.
