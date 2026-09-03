# 基地车工厂图纸观察 — 2026-08-31

状态：**OBSERVED，未自动支持。**  
这是给 Project Factory 用的上游图纸，不是已经发货的 Profile。

规则：成熟上游优先；配置 > 扩展 > 适配器 > 上游 PR > 最小补丁 > fork。  
Factory 不接管 Harness 循环。图纸用来生成**普通原生项目**。

## 已经在 0.14.1 车上的

| 图纸 | 上游 | 用法 |
|---|---|---|
| uv app/lib src 布局 | [uv init](https://docs.astral.sh/uv/concepts/projects/init/) | python-cli / python-library |
| npm 包 | npm | node-library / browser-extension-js |
| Codex / Claude 说明文件 | AGENTS.md / CLAUDE.md | harness 兼容，不是 runtime |
| Dagu DAG | dagu | Runner Provider，不并进 Core |

## 建议下一刀收集进配方的

### 1. 官方 MCP Python SDK v2

- 仓库：https://github.com/modelcontextprotocol/python-sdk
- 文档：https://py.sdk.modelcontextprotocol.io/get-started/first-steps/
- 图纸：`src/{pkg}/server.py` + `MCPServer` + `@tool` / `@resource` / `@prompt` + `uv` + pytest
- 对应未来 Profile：`python-mcp-server`
- 验证：pytest；`mcp dev` 只算开发器，不算 VERIFIED

### 2. WXT 浏览器扩展

- 文档：https://wxt.dev/guide/essentials/project-structure
- 图纸：`wxt.config.ts` + `entrypoints/` + Vite + `.output/` zip
- 比手写 MV3 更像成熟产线，可作为 `browser-extension-js` 的可替换继任者

### 3. Copier

- 文档：https://copier.readthedocs.io/en/latest/comparisons/
- 图纸：模板仓库 + `.copier-answers.yml` + `copier update`
- 用来叠 Factory 自己的 overlay（验证脊、AGENTS.md），语言根仍用 uv/npm

### 4. Pydantic AI（生成物，不是工厂大脑）

- 仓库：https://github.com/pydantic/pydantic-ai
- 图纸：`Agent` + `deps_type` + tools + TestModel
- 生成 *agent 应用项目*。禁止把 Pydantic AI 做成 Factory 自己的模型循环。

## 明确不收进 Core

LangChain / CrewAI / AutoGPT 一类厚运行时。观察到 latest ≠ 自动支持。

完整机器可读条目见同目录 `2026-08-31-base-vehicle-blueprints.yaml`。
