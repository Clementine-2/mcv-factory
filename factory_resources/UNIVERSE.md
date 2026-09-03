# 工厂资源宇宙

**阶段 A（种类+轮子账）：通过，但不是终局。**  
**阶段 A.1（可组合模型+覆盖夹具）：进行中，只建账，Core 0.14.1 未改。不开阶段 B。**

A 解决了「世界上有哪些常见成品、有哪些成熟轮子」。  
A.1 解决「任意一个真实项目，如何用有限、稳定、可组合的维度描述」。

**已经收回的说法：** 「大约 99% 项目类型」。那个数字没有可验证定义。覆盖率只看 `coverage_fixtures/`。

宪法：`work/FACTORY_CONSTITUTION.md`  
坐标纸：`PROJECT_SPEC.md`  
机器账：`universe/`（00–17 + schema）  
代表需求：`coverage_fixtures/corpus.yaml`（120 条）  
上网出处（轮子调研）：`universe/SOURCES.md`。

---

## 先把四个字分清

| 词 | 干什么 | 现在这张账里 |
|---|---|---|
| **工厂** | 整个产品 | 产品本身 |
| **机床** | 造工厂的工具（窗口、安装器、内核） | `universe/07_factory_self.yaml` |
| **仓库** | 存放资源，不执行 | 本目录 |
| **产线** | 真能生成项目的 Profile | 仍只有四条 owned |

网上有个框架 ≠ 厂里有条产线。仓库可以很满，车间可以还只有四台机床在转。这是故意的。

**A.1 起，一个项目是坐标，不是种类名。**  
What × 执行 × 语言 × 车身 × 状态 × 集成 × 交付 × 仓拓扑 × 质量 × 安全 × 运维 × 兼容 × 生命周期。  
`FastAPI+React+Postgres+...` 是多个轴上的取值，禁止变成一条新产线名。

---

## 已经钉在车上的（owned，0.14.1）

1. Python CLI（车身 argparse）
2. Python 库
3. Node 库
4. 手写 MV3 扩展（真机浏览器 claim 故意未验证）

物料钉：uv 0.10.0、npm 10.9.2。看见 0.12 / 12.x 只记观察。  
内核依赖只有 jsonschema、PyYAML。  
说明书：每个生成项目写 AGENTS.md / CLAUDE.md。

---

## 工作产品槽位（种类覆盖）

完整表：`universe/01_work_products.yaml`。人话压缩：

**日常会被点名的（observed，有轮子，无产线）**

- 终端：CLI、TUI
- 包：多语言 library / crate / module
- Web：SPA（Vite+React/Vue/Svelte）、SSR（Next/Nuxt/SvelteKit/Astro）、静态站、文档站、设计系统
- 服务：HTTP、GraphQL、gRPC、实时、后台 Worker、定时任务
- Agent 工具车：MCP server / client（工厂自己不当 Host）
- 桌面：Tauri / WPF / WinUI / Avalonia / Qt / SwiftUI；Electron 只给用户项目垫底
- 移动：Flutter、Expo/RN、KMP、双端原生
- 扩展：浏览器扩展、VS Code 扩展
- 数据：笔记本、实验、ML 训练、数据管道、dbt 变换
- 基础设施：IaC、容器编排 overlay、monorepo
- 系统向：WASM、原生扩展（maturin/napi）、嵌入式
- 其它常见小品：Bot、爬虫、独立 E2E 仓库、API 合同仓、多语言仓

**有意放后的长尾（deferred，不是假装没有）**

WordPress 主题、Office 插件、K8s Operator、区块链、AR/VR、Rails、油猴脚本、编译器工具链。

夹具里早就在问、但还没产线的，仍然是：Web 前后端（03）、笔记本（04）、桌面+Rust（05）。它们现在对得上槽位了，还是没有 Profile。

---

## 每个类目装进来的成熟轮子

原则：官方脚手架优先；每个类目 2–4 个；不并行三条继任者。

| 类目 | 首选轮子 | 备选 | 不并行 / 不进机床 |
|---|---|---|---|
| Python CLI 车身 | Typer | Click、argparse（已有） | Typer 不是新 Harness |
| Go / Rust / Node CLI | Cobra / Clap / Commander | oclif（重型 Node） | |
| TUI | Textual、Ratatui、Bubble Tea、Ink | | |
| Python HTTP | FastAPI 最小骨架 | Django（重后台）、Flask（存量） | 官方全栈 FastAPI 模板太重 |
| TS HTTP | NestJS | Hono（边缘）、Express（存量） | |
| 其它 HTTP | Spring Boot、ASP.NET Core、Axum、Chi/Gin | Ktor、Laravel | |
| SPA | create-vite：React / Vue / Svelte / Solid | Angular 存量 | CRA 已死，不收 |
| SSR / 内容 | Next、Nuxt、SvelteKit、Astro | Remix 并入 RR7，只观察 | |
| 浏览器扩展 | **WXT** | Plasmo、Extension.js 候选 | 三选一继任，旧手写 MV3 先留 |
| MCP | 官方 Python/TS/C#/Go SDK（Tier 1） | Rust/Java/Kotlin | 工厂 ≠ Host；`mcp dev` 是开发器 |
| 桌面 | Tauri、WPF/WinUI、Avalonia | Flutter Desktop、Qt、Wails | Electron 禁止当机床 |
| 移动 | Flutter、Expo、KMP | 双端原生 Compose/SwiftUI | Ionic 不进三强 |
| 数据科学结构 | Cookiecutter Data Science | Kedro | |
| 管道 / 变换 | Dagster、Prefect、dbt | Airflow 存量 | |
| IaC | OpenTofu、Pulumi | Terraform BSL 只观察、CDK 单云 | |
| 游戏 | Godot、Bevy | Unity 闭源只记 | |
| 编辑器扩展 | `yo code`（官方） | | |
| 量具加法 | pytest、ruff、Vitest、Playwright、Biome | Cypress 不与 Playwright 双默认 | 本地门仍是权威 |
| 模板更新 | Copier overlay | Cookiecutter 一次成型 | Copier 不替换 uv/npm |
| 技能包 | SKILL.md + agentskills.io | | 不覆盖 Canonical |
| JS 包管理多样性 | pnpm（monorepo 基线）、Bun（runtime 观察） | Yarn | 现钉仍是 npm |

语言根除已有 Python/JS，仓库补了 TypeScript、Rust、Go、C#、Java、Kotlin、Dart、Swift、C++、PHP。Ruby/Elixir/Zig 等放 deferred。

---

## 机床（工厂自己）

.NET 10 + WPF-UI 4.3 + NSIS 3.12 + 有界 JSON 桥 + 内核 0.14.1。  
用户 2026-08-31：**外壳粗糙但基本能用，现在通过，以后打磨。**  
机床依赖和用户项目依赖必须两套钉。生成仓库里不准出现机床代码。

---

## 代码以后怎么长（现在就生效的项目级要求）

详见 `work/FACTORY_ONTOLOGY.md`。

- 新产线 = 新插件，不要在内核里 `if kind == "mcp"`。
- 仓库记账，车间执行，内核裁决，外壳展示。
- 能力 ≠ 供应商。`observed_latest ≠ supported`。
- 一层一个目录。生成不写进验证，验证不写进注册表，注册表不写进窗口。

阶段 A **不改代码**。这份合同是下一刀 0.14.2 的开工条件。

---

## 还没装进产线、但账已经能接的下一刀（提醒，不是开工）

阶段 B 仍是 `python-mcp-server`（官方 SDK + uv）。  
扩展继任者账上已收窄到 WXT 优先。  
FastAPI 最小服务对齐夹具 03。  
这些都要你点头才切钢板。

---

## 验收词（A.1）

「随机给出一个主流项目需求，现有 ontology 能自然描述它；组合栈不会逼出新 kind。」

不是「又加入 30 个框架」。阶段 B 仍冻结，直到这句点头。
