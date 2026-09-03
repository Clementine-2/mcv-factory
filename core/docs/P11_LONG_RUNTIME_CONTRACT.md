# P11 Long Runtime Contract

Stage: P11 Long Runtime
Factory: 0.12.0
Project Lock schema: 0.9
Runner contract schema: 0.1

## Purpose

Long-running execution is an optional Capability/Provider boundary. It repeatedly invokes finite Agent batches without requiring one Agent session to remain alive indefinitely.

Required topology:

`OS/service -> Runner Provider -> Harness CLI -> Generated Project`

Interactive Hosts remain a peer path:

`Interactive Host -> Harness -> Generated Project`

The Runner path must not route scheduler ownership through AionUI or another Interactive Host.

## Default

No Runner is materialized for normal interactive or batch projects. Runner materialization requires an execution decision with `autonomy=long-running`. This preserves the no-framework-tax invariant.

## Provider boundary

P11 ships one Runner Provider contract: `dagu`.

Project Factory:

- selects the Provider through the Runner Registry;
- generates a bounded Dagu DAG;
- records plan hash and Provider provenance in Project Lock/Evidence;
- verifies Runner materialization and rejects plan tampering;
- can perform explicit `validate`, `start`, `status`, and `stop` adapter calls;
- does not install, download, auto-update, daemonize, or silently launch Dagu;
- does not embed Dagu source.

Dagu owns execution lifecycle while it is actually running: process execution, timeout, retry, repeat, run state/history and step scheduling.

The Harness owns model/tool/session behavior.

Project Factory owns policy, Verification semantics, Evidence, Project Lock, upgrade boundaries and Factory-mediated admission.

The Agent owns neither completion truth nor Runner lifecycle.

## Bounded batch model

Default generated limits:

- wall-clock timeout: 14,400 s;
- per-batch timeout: 1,800 s;
- maximum batches: 8;
- interval between batches: 5 s;
- retry limit: 1;
- retry interval: 30 s;
- retry maximum interval: 120 s;
- Dagu active steps per run: 1.

All limits are bounded and validated before plan generation. P11 does not expose unlimited retry or unlimited wall-clock operation.

Each Agent invocation receives exactly one coherent engineering batch. At batch end it writes `.project/runner/state/LAST_BATCH.md` with observed work/evidence/remaining work/next batch guidance.

## Completion truth

`.project/runner/state/CANDIDATE_DONE.flag` is an Agent claim only. It controls the repeat condition but is not verification truth.

After the candidate flag appears, generated command gates still run. Project Factory Verification remains authoritative for project claims.

A successful `dagu start` command is execution evidence only. `start_runner()` therefore reports `START_COMMAND_COMPLETED` or `START_COMMAND_FAILED` and always keeps:

- `workflow_completion_verified=false`;
- `runtime_verified=false`.

P11 deliberately does not infer long-run success from a process return code, a status file, or Agent self-report.

## Concurrency

Dagu v2.11.2 keeps `max_active_runs` in its schema but explicitly marks it deprecated/ignored for local DAG-based queues. P11 does not use that field as the local concurrency authority.

The generated DAG still sets `max_active_runs: 1` as an additional compatibility constraint and `max_active_steps: 1` for within-run step serialism.

For explicit local `project_factory runner start`, Factory holds an OS advisory lock at `.project/runner/state/ACTIVE_RUN.lock` for the foreground start execution. A second overlapping Factory-mediated start for the same project is rejected.

The admission lock is runtime state, not Factory overlay state and not a backup.

## Working directory

The Dagu DAG is stored at `.project/runner/dagu.yaml`. Dagu resolves relative `working_dir` from the DAG file location, so the generated plan uses `working_dir: ../..` to execute in the generated project root.

## Recovery state

- `LAST_BATCH.md` is an advisory continuation checkpoint.
- `CANDIDATE_DONE.flag` is an Agent claim.
- `ACTIVE_RUN.lock` is transient admission state.
- Dagu logs/history are Provider operational state.

None of these are independent disaster recovery. Project Factory stage checkpoints remain separate recovery artifacts.

## Safety boundaries

P11 forbids the Runner layer from:

- choosing project architecture;
- editing Blueprint semantics by itself;
- owning Extension state;
- owning Interactive Host state;
- owning Harness runtime semantics;
- changing Verification truth;
- writing Project Lock outside the Factory lifecycle;
- installing/upgrading Dagu automatically;
- executing destructive retry loops without explicit project commands and bounds.
