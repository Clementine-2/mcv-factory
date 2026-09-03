# text-normalizer-lib

做一个 Python library，提供可复用的文本标准化能力，长期维护。

## Status

Factory-generated `python-library` project scaffold. Verification is evidence-scoped; see `.project/evidence/generation-verification.json`. Domain-specific functionality is intentionally not implemented by the Factory.

## Verification

```bash
uv --offline run python -c import text_normalizer_lib; print(text_normalizer_lib.scaffold_status())
```
```bash
uv --offline run python -m unittest discover -s tests -v
```
```bash
uv --offline build
```

## Agent development

Read the generated native harness context file(s). Every harness context is generated from `.project/contract/agent-contract.md`. Provenance is stored in `project.lock.json` and `.project/`.
