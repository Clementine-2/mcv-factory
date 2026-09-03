# cross-browser-helper

做一个 JavaScript 浏览器扩展，必须支持 Chrome 和 Firefox，先建立可靠项目基地。

## Status

Factory-generated `browser-extension-js` project scaffold. Verification is evidence-scoped; see `.project/evidence/generation-verification.json`. Domain-specific functionality is intentionally not implemented by the Factory.

## Verification

```bash
npm run check:manifest
```
```bash
npm test
```
```bash
npm pack --ignore-scripts
```

## Agent development

Read the generated native harness context file(s). Every harness context is generated from `.project/contract/agent-contract.md`. Provenance is stored in `project.lock.json` and `.project/`.
