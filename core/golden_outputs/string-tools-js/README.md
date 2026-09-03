# string-tools-js

做一个 JavaScript library，提供可复用的字符串处理能力，长期维护。

## Status

Factory-generated `node-library` project scaffold. Verification is evidence-scoped; see `.project/evidence/generation-verification.json`. Domain-specific functionality is intentionally not implemented by the Factory.

## Verification

```bash
node --input-type=module -e import('./src/index.js').then(m => console.log(m.scaffoldStatus()))
```
```bash
npm test
```
```bash
npm pack --ignore-scripts
```

## Agent development

Read the generated native harness context file(s). Every harness context is generated from `.project/contract/agent-contract.md`. Provenance is stored in `project.lock.json` and `.project/`.
