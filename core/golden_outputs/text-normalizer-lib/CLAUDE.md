# Agent Contract — text-normalizer-lib

## Project purpose

做一个 Python library，提供可复用的文本标准化能力，长期维护。

## Bootstrap state

This repository is a Factory-generated `python-library` scaffold. Verification is claim-scoped; inspect `.project/evidence/generation-verification.json` before treating any behavior as verified. The Factory has **not** implemented domain-specific behavior.

## Native layout

- source: `src/text_normalizer_lib/`
- tests: `tests/`
- packaging: `pyproject.toml`
- project metadata: `.project/`

## Verification commands

- `uv --offline run python -c import text_normalizer_lib; print(text_normalizer_lib.scaffold_status())`
- `uv --offline run python -m unittest discover -s tests -v`
- `uv --offline build`

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
