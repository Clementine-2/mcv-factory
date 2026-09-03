# P11 Closeout

Stage: P11 Long Runtime
Factory: 0.12.0
Project Lock schema: 0.9
Runner contract schema: 0.1

## Delivered

- optional `long_running_execution` Capability/Provider boundary;
- versioned Runner Registry with Dagu v2.11.2 contract provenance;
- bounded Dagu DAG generation for Codex/Claude Harness adapters;
- finite batch/repeat/timeout/retry model;
- explicit Project Factory Verification gates after candidate completion;
- Runner plan hash in Project Lock and tamper detection on restore;
- Factory-mediated same-project admission lock for explicit local start;
- `runner inspect|validate|start|status|stop` CLI;
- start-command truth semantics that never equate process success with workflow completion;
- Runner Matrix for Python and Node long-running projects;
- controlled fake-Dagu Adapter lab;
- P10->P11 four-project upgrade matrix;
- four standard Golden Projects proving default no-Runner behavior;
- Factory 0.12.0 wheel outside-source smoke including Runner package data.

## Verified before checkpoint finalization

- full automated suite: 193/193 PASS after Runner integration before final restore;
- Runner-specific suite: 16/16 PASS after command-success truth correction;
- Runner Matrix: PASS for Python CLI + Node library, plan/restore scope only;
- controlled fake-Dagu lab: PASS for version -> validate -> dry -> start -> status -> stop ordering and fail-closed plan hash/admission behavior;
- P10->P11 upgrade matrix: PASS, old projects not silently given Runner, user source preserved, first project exact rollback;
- standard P11 Golden Matrix: PASS, all four defaults remain Runner-free;
- Factory wheel smoke: PASS outside source tree; P11 package files present; long-running project generated/restored; runtime correctly unavailable.

## Truth boundary

P11 verifies the Runner contract/materialization/Adapter boundary, not a real unattended Agent shift. Current environment lacked Dagu/Codex/Claude and could not download the official Dagu archive because outbound container network resolution was unavailable.

Consequently live Dagu + Harness long-run execution remains UNVERIFIED and must not be described as completed.

## Candidate clean restore

Candidate checkpoint SHA256 `f8bc5bc3957056add1b9be5035f84df9abd574e7065bc3ada3d1c152bfca8a6a` passed 619/619 manifest, 193/193 tests, Runner Matrix, fake-Dagu Adapter Lab, P10->P11 upgrade matrix, standard Golden Matrix with no default Runner surface, and outside-source wheel smoke. The final delivered ZIP is separately verified by exact SHA and external restore evidence.
