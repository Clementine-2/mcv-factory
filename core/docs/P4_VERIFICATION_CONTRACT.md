# P4 Verification Spine Contract

## Purpose

P4 separates scaffolding from verification and makes completion claims evidence-scoped.

## Core chain

```text
Verification Suite
  -> Gate execution
  -> Evidence
  -> Claim evaluation
  -> Scoped verification status
```

## Gate semantics

A Gate has an id, target, method, expected result, observed result, required flag and evidence level.

Current trusted methods:

- `command`: run a trusted command and evaluate return code plus optional output assertions.
- `artifact`: inspect actual generated artifact paths and record SHA256.

Registry data may select a suite id, but it cannot inject arbitrary commands. Trusted executable definitions remain code-reviewed adapters.

## Evidence levels

- `EXECUTED`: the check actually ran, but it did not satisfy the gate.
- `PASSED`: the check ran and satisfied the declared expectation.

A failed command must never be rendered as a passing gate.

## Claim statuses

- `VERIFIED`: all declared evidence gates for that claim passed.
- `PARTIALLY_VERIFIED`: mixed evidence exists.
- `UNVERIFIED`: no evidence gate covers the claim.
- `FAILED`: the claim's evidence gates failed.

A claim with no gate cannot become `VERIFIED` by assertion alone.

## Report status

- `FAILED`: a required gate failed or a material claim failed.
- `PARTIALLY_VERIFIED`: required gates passed, but a material claim remains unverified/partial.
- `VERIFIED`: required gates passed and all material claims are verified.

`VERIFIED` is always scoped by the suite's explicit scope and limitations.

## Browser example

For the JavaScript browser-extension scaffold:

Verified locally:

- Manifest V3 static structure.
- JavaScript smoke tests.
- Local package creation.

Unverified:

- Real Chrome runtime compatibility.
- Real Firefox runtime compatibility.

Therefore its overall generation verification is `PARTIALLY_VERIFIED`, not a global PASS.

## Architectural boundary

`recipes.py` owns trusted scaffolding behavior.

`verification.py` owns trusted verification suites, gates, evidence and claims.

`factory.py` orchestrates them and must not embed concrete gate ids.
