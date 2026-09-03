# P10 Retrospective Audit

## Course check

Status: ON COURSE.

P10 did not add a model loop, session manager, scheduler, GUI runtime, Agent team, package installer, or Host-specific private project framework.

The Core remains responsible for project semantics, composition, evidence and recovery. The new Host boundary is isolated in `host.py` plus metadata in `hosts.yaml`.

## Drift controls added

- `factory.py` may not embed the AionUI product id.
- `host.py` may not use subprocess/package installation or import Extension/Verification/Process ownership layers.
- `hosts.yaml` may not contain arbitrary launch/install commands.
- Host Registry rejects ownership of Extensions, Verification, Runner, Harness runtime or Project Lock.
- Host is opt-in to avoid framework tax.
- Host runtime cannot become VERIFIED from file generation alone.

## Current size signal

Python Core is approximately 6.1k LOC. `host.py` is about 277 LOC. The Host layer is currently thin enough; P11 must not route long-runtime lifecycle through `host.py` or `factory.py`.

## Remaining limits

- AionUI live GUI runtime is unverified in this environment.
- Codex/Claude live task execution remains unverified here.
- ACP transport itself is owned by the Host/Harness ecosystem, not reimplemented by Factory.
