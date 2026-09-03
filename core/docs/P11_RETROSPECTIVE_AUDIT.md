# P11 Retrospective Audit

Stage: P11 Long Runtime

## Question 1 — Did Factory become a Runner?

No. Scheduling/process lifecycle remain behind an optional Runner Provider. The Factory only owns contract generation, admission for its explicit start path, verification boundaries, provenance and migration.

## Question 2 — Did Runner become an Interactive Host?

No. AionUI remains a peer interactive path. Runner code does not import/launch Host code, and the generated Runner contract states the separation explicitly.

## Question 3 — Did P11 recreate the old heavy AgentRunner control plane?

No. P11 reuses the useful requirement: wall clock, bounded batch continuation, heartbeat/run state responsibility, timeout, retry, checkpoint continuation and lifecycle control belong outside project business logic. It does not recreate lease/provider-authority/gatekeeper/worker hierarchies or a model loop.

No legacy AgentRunner implementation was imported into Factory Core.

## Question 4 — Is Dagu hard-coded into project semantics?

No. Blueprint remains Provider-neutral. `dagu` appears in the Runner Registry and generated Provider materialization only. Factory Core selects the capability boundary without embedding the product id.

## Question 5 — Did default projects acquire framework tax?

No. Four standard P11 Golden Projects remain `runner_status=NOT_CONFIGURED`; no `.project/runner/` surface is generated unless long-running autonomy is selected.

## Question 6 — Are completion claims evidence-safe?

Yes after a P11 audit correction. An early implementation returned `runtime_verified=true` when a fake `dagu start` exited zero. That was rejected because command success is not long-run/project success. Final P11 reports start command completion separately and leaves workflow/runtime verification false unless stronger evidence exists.

`CANDIDATE_DONE.flag` is explicitly non-authoritative.

## Question 7 — Is same-project local concurrency actually guarded?

Partially and explicitly scoped. Dagu v2.11.2's local `max_active_runs` is not relied upon. Factory uses an OS advisory lock for its explicit foreground `runner start` path, and Dagu `max_active_steps=1` serializes steps inside a run.

P11 does not claim a cross-host/global distributed singleton guarantee.

## Question 8 — Did P11 invent unverified Dagu YAML?

No known unsupported fields remain in the generated plan. During development, `working_dir: .` was corrected to `../..`, verification gates were corrected to canonical `action: exec`, and unneeded Provider artifact configuration was removed from the generated plan. The final field set is tied to v2.11.2 tag evidence.

## Question 9 — Is recovery being confused with sync/runtime state?

No. Dagu logs/history and `.project/runner/state/*` are operational/continuation state only. P11 completion still requires a separate checkpoint ZIP, manifest, exact SHA and fresh-extraction restore test.

## Audit verdict

PASS WITH EXPLICIT RUNTIME LIMITATION.

The architecture remains aligned with P0 invariants. The main remaining P11 limitation is environmental: no real Dagu/Codex/Claude long-running runtime was available for a live end-to-end run in this execution environment.
