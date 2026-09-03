# P3 Registry Contract

## Scope

P3 replaces P2 profile/provider hard-coding with small declarative registries. The registry is not a plugin marketplace and does not execute arbitrary code from registry data.

## Rules

- Core depends on capability IDs, not provider product names.
- Profiles declare semantic match rules, required capabilities, provider preferences, scaffold recipe ID, verification recipe ID, and materialization hint.
- Provider records declare executable discovery and tested versions. A provider version not listed as tested is rejected in P3 rather than silently treated as supported.
- Recipes are code-owned trusted adapters; registry data may select them but may not contain executable shell snippets.
- Provider source remains unmodified. Integration is through public CLI only.
- Ambiguous equal-priority profile matches are a visible error, never first-match wins.
- Missing provider executables and untested provider versions are visible blockers; P3 does not auto-install or auto-upgrade tools.

## P3 supported project families

1. python-cli -> uv
2. python-library -> uv
3. node-library -> npm
4. browser-extension-js -> npm

These are compatibility proofs, not claims of universal support.
