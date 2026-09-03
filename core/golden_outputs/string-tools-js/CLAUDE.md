# Agent Contract — string-tools-js

## Project purpose

做一个 JavaScript library，提供可复用的字符串处理能力，长期维护。

## Bootstrap state

This repository is a Factory-generated `node-library` scaffold. Verification is claim-scoped; inspect `.project/evidence/generation-verification.json` before treating any behavior as verified. The Factory has **not** implemented domain-specific behavior.

## Native layout

- source: `src/`
- tests: `tests/`
- packaging: `package.json`
- project metadata: `.project/`

## Verification commands

- `node --input-type=module -e import('./src/index.js').then(m => console.log(m.scaffoldStatus()))`
- `npm test`
- `npm pack --ignore-scripts`

## Extension resources

- No Factory extensions are enabled for this project.

Extension resources are additive. They do not override this canonical contract or the Verification Spine.

## Hard project constraints

- No additional project-specific hard constraint was explicit in the Blueprint.

## Engineering discipline

- Do not claim completion from an Agent statement alone; attach execution evidence.
- Prefer native ecosystem tooling and existing dependencies over inventing infrastructure.
- Do not introduce a Runner, multi-Agent team, or new framework unless the task demonstrates a need.
- Preserve the original Blueprint and Project Lock as provenance.
- Destructive or irreversible operations require an explicit recovery plan.
- Harness-specific files are adapters over this same contract; do not create conflicting per-harness rules.

## Factory upgrade discipline

- Treat Factory upgrades as explicit migrations, never as automatic dependency refreshes.
- Inspect the DryRun plan and rollback scope before applying Factory-owned overlay changes.
- A Factory-owned file that diverged from its recorded preimage is a conflict; do not overwrite it silently.
- Business/source files are outside the Factory overlay unless a future migration explicitly declares otherwise.
