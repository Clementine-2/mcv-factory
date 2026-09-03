# json-batch-cli

做一个 Python 命令行工具，批量读取一个目录里的 JSON 并转换格式。不能覆盖原始文件。

## Status

Factory-generated `python-cli` project scaffold. Verification is evidence-scoped; see `.project/evidence/generation-verification.json`. Domain-specific functionality is intentionally not implemented by the Factory.

## Verification

```bash
uv --offline run json-batch-cli
```
```bash
uv --offline run json-batch-cli --version
```
```bash
uv --offline run python -m unittest discover -s tests -v
```
```bash
uv --offline build
```

## Agent development

Read the generated native harness context file(s). Every harness context is generated from `.project/contract/agent-contract.md`. Provenance is stored in `project.lock.json` and `.project/`.
