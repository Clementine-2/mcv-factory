# 本轮宇宙账的上网来源

阶段 A 扩账。闭门造车禁止。下面是 2026-08-31 实际打开过的公开调查和官方脚手架，不是印象。

## 调查（用来决定「哪几个算最成熟」）

- JetBrains State of Developer Ecosystem 2025：主语言 Python / Java / JS / TS；Promise Index 上 TS、Rust、Go。
  https://blog.jetbrains.com/research/2025/10/state-of-developer-ecosystem-2025/
- Stack Overflow Developer Survey 2025：Python +7pt；uv 最受钦佩 tag；Cargo 最受钦佩基础设施工具；Docker 71%。
  https://survey.stackoverflow.co/2025
- SO 2025 Web 技术用量（Statista 转写）：Node 48.7、React 44.7、jQuery 23.4、Next 20.8、Express 19.9、ASP.NET Core 19.7、Angular 18.2、Vue 17.6、FastAPI 14.8、Spring Boot 14.7、Flask 14.4。
  https://www.statista.com/statistics/1124699/worldwide-developer-survey-most-used-frameworks-web/
- State of JavaScript 2025：前端 99%、后端 66%、移动 25%；Node 主导，Bun 第三。

## 官方脚手架（优先于社区二手模板）

- uv init：https://docs.astral.sh/uv/concepts/projects/init/
- create-vite 9.2.0：vanilla/vue/react/svelte/solid/preact/lit/qwik ± ts
- create-next-app 16.3.3：可生成 AGENTS.md
- create-vue、create-astro 5.2.4、Nest `nest new`、Spring Initializr
- MCP 官方 SDK 分档：https://modelcontextprotocol.io/docs/sdk
  Tier 1：TS / Python / C# / Go（Rust 在不同镜像页档位略有出入，以官方表为准）
  Python SDK v2：https://github.com/modelcontextprotocol/python-sdk
- WXT 对比 Plasmo / CRXJS：https://wxt.dev/guide/resources/compare
- Playwright `npm init playwright@latest`：https://playwright.dev/docs/intro
- VS Code `yo code`：https://github.com/microsoft/vscode-generator-code （1.12.0，2026-06）
- Copier vs Cookiecutter：Copier 可 update；Cookiecutter 一次成型

## 类目对比（用来选每槽 2–4 个轮子，不是选唯一真理）

- CLI：Typer / Click / Cobra / Clap / Commander（kubectl/docker/gh 与 ripgrep/bat 路线）
- 桌面 2026：Tauri 轻、Electron 重、Flutter 自绘、WPF/WinUI Windows 原生、Avalonia 跨平台 C#
- 移动 2026：Flutter / React Native+Expo / Kotlin Multiplatform 三强
- 数据：Cookiecutter Data Science、dbt、Dagster、Prefect、Airflow
- IaC：OpenTofu（开源优先）、Pulumi、Terraform BSL 只观察
- 扩展：2026 新项目默认 WXT；Plasmo 维护变慢，作候选不并行
- 游戏：Godot（开源成熟）、Bevy（Rust）、Unity 只记闭源主流
- Monorepo：pnpm workspaces 基线，Turborepo / Nx 编排

## 有意没当「最成熟轮子」装进来的

jQuery（用量高但不是新项目车身）、Create React App（已被 Next/Vite 取代）、AngularJS、Electron 作机床、LangChain 作内核、Ionic 作移动首选、WordPress 作近阶段产线。
它们在账上要么 deferred，要么 out_of_universe，避免假装没看见。
