# P3 Profiles & Scaffolding System Closeout

## Status

P3 is COMPLETE for the registry-driven scaffolding architecture and the four explicitly tested project families listed below.

## What P3 proves

- Profile selection is registry-driven instead of a growing `if/elif` chain in Factory Core.
- Capability selection and Provider selection are separate concepts.
- Provider resolution rejects missing executables and untested versions instead of auto-installing or silently upgrading them.
- Registry data cannot contain arbitrary executable commands; trusted Recipe Adapter code owns command construction.
- Factory Core does not embed concrete Profile or Recipe IDs. A regression test enforces this boundary.
- Provider source remains unmodified. Current integrations use public CLIs only.
- Generated projects record Profile, Capability, Provider, Factory version, verification recipe, verification environment, Evidence, and known limitations.
- Four materially different Golden Projects can be generated, independently extracted, manifest-verified, and locally re-verified.

## Supported P3 profiles

| Profile | Work product | Technology | Scaffolder Provider | Verification |
|---|---|---|---|---|
| `python-cli@0.2` | CLI | Python | `uv 0.10.0` | offline run/version/unit tests/build |
| `python-library@0.1` | library | Python | `uv 0.10.0` | offline import/unit tests/build |
| `node-library@0.1` | library | JavaScript | `npm 10.9.2` | Node import/test + npm pack |
| `browser-extension-js@0.1` | browser extension | JavaScript | `npm 10.9.2` | manifest structure + Node smoke test + npm pack |

Verification runtime observed in this checkpoint:

- Python 3.13.5
- Node v22.16.0

These are observed/tested versions, not claims that they are the latest upstream releases.

## Verification scope limitation

`VERIFIED` in P3 is scoped to the Factory-generated bootstrap scaffold and its local verification recipe.

It does **not** mean:

- a Python artifact was published to or installed from PyPI;
- a Node package was published to or installed from the public npm registry;
- the browser extension was actually launched in Chrome and Firefox.

For the browser extension, Manifest V3 structure, package contents, and JavaScript smoke behavior are verified, while real cross-browser runtime compatibility remains unverified.

## Registry architecture

```text
Blueprint
   -> Profile Registry
   -> Capability requirements
   -> Provider Registry
   -> tested Provider runtime
   -> trusted Recipe Adapter
   -> Project materialization
   -> Verification + Evidence
```

Registry files live in `src/project_factory/registry_data/` and are packaged with the Factory wheel.

## Native Ecosystem First evidence

Current Provider choices use mature native ecosystem entry points:

- Python applications/libraries: `uv init`
- JavaScript package baseline: `npm init`

No `uv`, `npm`, Node, or browser source is vendored or forked into the Factory.

## Deliberately unsupported in P3

- TypeScript browser-extension generation (no tested reproducible local TypeScript toolchain contract yet)
- web framework projects
- API/service frameworks
- research/notebook generation
- desktop apps
- monorepos
- Copier integration
- Spec Kit integration
- production LLM semantic normalization
- Harness adapters
- Runner/AionUI integration
- existing-project upgrade
- GUI

Unsupported inputs must block visibly rather than silently falling back to a different profile.

## Architecture outcome

The important P3 result is not “four templates”. It is that adding a Profile which can reuse an existing trusted Recipe is now a Registry change rather than a Factory Core rewrite. New execution mechanics belong in a Recipe Adapter, not in the Core orchestration path.
