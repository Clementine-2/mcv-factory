# P∞ Global Retrospective + Human UX + Brutal Hardening

## Decision

Do not open P13 merely because P12 is complete. The retrospective found no evidence that the core architecture needs another numbered Core stage. The main product-level deficiency was the outer user surface: the root help/empty command dropped users into the Blueprint validator and common project creation required users to know internal command structure.

This iteration therefore stays in **P∞ Continuous Evolution** and changes UX, safety boundaries, timeout behavior, test pressure and recovery evidence without collapsing Harness/Host/Runner/Provider/Extension boundaries into Factory Core.

## 1. 已兑现

| Capability | Current evidence | Result |
|---|---|---|
| Intent/Blueprint/decision/Profile/Provider/native-project path | P2-P5 closeouts + Golden suites | Implemented and regression-tested |
| Independent verification spine | P4 onward verification tests and restore verification | Implemented |
| Harness-neutral contract with Codex/Claude adapters | P6 tests/Goldens | Implemented at contract/materialization layer |
| Compatibility truth model | P7 registry/lab tests | Tested vs supported remains explicit |
| DryRun-first upgrade + rollback | P8 plus P12→P∞ matrix | Implemented; user source preservation and exact rollback exercised |
| Extension boundary | P9 tests/wheel smoke | Declarative + explicitly trusted extension mechanisms implemented |
| Interactive Host boundary | P10 tests | Contract/materialization implemented without Factory taking runtime ownership |
| Long-runtime Runner boundary | P11 tests/fake lab | Contract/Adapter/materialization implemented without claiming live unattended success |
| Product doctor/bootstrap/checkpoint/release composition | P12 evidence | Implemented |
| Human common path | P∞ UX tests + wheel smoke | `status -> new -> check -> verify` implemented without removing advanced interfaces |
| Archive/manifest safety | P∞ targeted tests + brutal archive shard | traversal/backslash/symlink/overwrite boundaries hardened |
| Bounded external commands | P∞ timeout tests + brutal timeout shard | explicit timeouts; release-gate process tree termination |
| Concurrency/repetition pressure | P∞ brutal suite | same-name race fails closed; independent names can proceed; repeated checks remain stable |

## 2. 半兑现

| Capability | What is verified | What is not yet verified |
|---|---|---|
| LLM semantic interpretation | Deterministic semantic adapter/decision boundary exists | Production LLM semantic adapter is not integrated |
| Dagu/Codex/Claude long-runtime use | Runner contracts, plans, Adapter behavior and fake lab | Real authenticated unattended shift in a live environment |
| Browser-extension delivery | Generation/verification model and artifact contracts | Real Chrome + Firefox runtime execution in this environment |
| Local distribution | Wheel build, outside-source smoke, temporary-venv console script | Fully offline clean install with a bundled third-party wheel mirror |
| Reproducible build | Wheel content/function smoke | Byte-for-byte reproducible wheel across clean builds/environments |
| External ecosystem compatibility | Registry/extension/harness boundaries exist | Broad real third-party ecosystem interoperability |

## 3. 未兑现

These are not disguised as defects that must immediately become new Core work:

| Item | Current status | Re-entry trigger |
|---|---|---|
| Production LLM semantic adapter | NOT IMPLEMENTED | A concrete use case requires semantic inference that deterministic normalization cannot safely express |
| Real authenticated overnight Runner dogfood | UNVERIFIED | Dagu plus an authenticated supported Harness is available for a controlled run |
| Real Chrome/Firefox runtime matrix | UNVERIFIED | Browser runtime lab/environment is available |
| Fully offline dependency bundle | NOT IMPLEMENTED | Distribution requirement explicitly demands offline installation |
| Byte-for-byte reproducible wheel | UNVERIFIED | Reproducible-build requirement becomes a release criterion |

## User-layer correction

Before this iteration:

- root `--help` exposed BlueprintValidator help;
- empty invocation produced a missing-blueprint error;
- the common generation path required `generate --name --output-dir ...` and returned machine-oriented JSON;
- safe local check vs full ZIP restore verification were not presented as a simple user journey.

After this iteration:

```text
project-factory status
project-factory new NAME REQUIREMENT
project-factory check PROJECT_DIR
project-factory verify PROJECT.zip
```

The advanced/machine commands remain available for compatibility. Human commands support `--json` instead of forcing JSON on the default experience.

## Safety hardening added in P∞

- bounded requirement length and project-name length;
- accurate project-name contract/error text;
- project ZIP path traversal/backslash/symlink/duplicate/member-count/member-size/total-size checks;
- safe manual project restore instead of blind `extractall`;
- checkpoint ZIP equivalent path/symlink/size protections;
- read-only overlay/harness/runner/extension manifest path validation;
- atomic ZIP create/refuse-overwrite behavior;
- subprocess timeouts across recipes, verification, registry/provider probes, runner/process/compatibility and release scripts;
- release-gate child process-tree kill on timeout;
- bounded, resumable brutal test shards.

## Current evidence before final checkpoint freeze

- baseline P12 checkpoint ZIP CRC: PASS (restoration session evidence);
- baseline P12 manifest: 760/760 match (restoration session evidence);
- post-hardening targeted recovery/UX tests: 23/23 PASS;
- post-version-bump full suite: 224/224 PASS in 85.941s;
- P12 0.13.0 → P∞ 0.14.0 upgrade matrix: 4/4 PASS; user source preserved; first case exact rollback;
- P∞ 0.14.0 wheel smoke: PASS outside source tree and through an installed temporary-venv console script;
- earlier post-hardening brutal suite: 8/8 PASS; final checkpoint still requires the integrated nine-gate release run after documentation/freeze preparation.

## Architecture verdict

**ON COURSE, with product-surface correction.** The retrospective does not justify another Core stage. The correct next mode is P∞ dogfood/evolution with strict re-entry criteria for Core changes.
