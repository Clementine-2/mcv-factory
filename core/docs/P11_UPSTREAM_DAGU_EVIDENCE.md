# P11 Upstream Dagu Evidence

Observed/checked: 2026-08-30
Provider target: Dagu v2.11.2
Tag commit locked by Registry: `a1a3c286b26cbad934bb9f8344f2f9aa51385981`

## Release evidence

GitHub release `v2.11.2` was published 2026-07-31. The release includes `checksums.txt` and platform archives including Linux amd64.

Reference:

- https://github.com/dagucloud/dagu/releases/tag/v2.11.2

P11 does not pin to "latest". Registry support is explicitly scoped to the observed/tested contract version.

## Tag-level contract sources

The P11 contract was checked against exact-tag sources, not only the default branch:

- `skills/dagu/references/cli.md` — blob `7b8317423c77affed5b2c390727a5f0279ed4405`
- `skills/dagu/references/harnesses.md` — blob `096579d930671525aa324eaea729fdb4143481c8`
- `internal/cmn/schema/dag.schema.json` — blob `4ef76834fad926e2c97a1433e6f3e6dfc8fc98f0`
- `internal/cmd/start.go` — blob `d3913fc244de3e5fb8f314e23786b685247550a4`

All are referenced at commit `a1a3c286b26cbad934bb9f8344f2f9aa51385981`.

## Confirmed contract facts used by P11

Exact-tag evidence supports:

- `dagu validate` and `dagu dry` preflight commands;
- `dagu start`, `status`, `stop`, and `history` lifecycle commands;
- root `timeout_sec`;
- `max_active_steps`;
- `max_active_runs` field presence, while its schema explicitly says it is deprecated/ignored for local DAG-based queues;
- step/default retry and repeat policy structures;
- `action: harness.run` with built-in `codex` and `claude` providers;
- canonical action-based execution for generated verification gates;
- relative `working_dir` semantics tied to the DAG file directory.

The exact schema also supports an `artifacts` object with `enabled`/`dir`. P11 intentionally does not rely on Dagu artifact storage for Factory recovery because Provider artifacts/logs are operational state, not an independent Factory checkpoint.

## Start semantics

Exact-tag `internal/cmd/start.go` describes `dagu start` as executing a DAG and routes local execution through the DAG execution path. Project Factory still refuses to interpret a start command's return code as proof of project completion. The Adapter truth model remains stricter than simple process success.

## Runtime evidence boundary

This execution environment did not have `dagu`, `codex`, or `claude` installed. An isolated download of the official Linux amd64 archive was attempted but the container network could not resolve `github.com`; no system install or fallback package source was used.

Therefore:

- exact-tag static/provider contract: VERIFIED;
- Factory Adapter ordering/fail-closed behavior using controlled fake Dagu: VERIFIED;
- actual Dagu v2.11.2 binary execution in this environment: UNVERIFIED;
- actual Codex/Claude long-running engineering session under Dagu: UNVERIFIED.

See `evidence/P11_RUNTIME_ENVIRONMENT.txt` and `evidence/P11_FAKE_DAGU_LAB.json`.
