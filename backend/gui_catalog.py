"""GUI catalog. Labels for humans; ids stay Factory-owned."""

from __future__ import annotations

from typing import Any


def _item(id: str, label: str, demand: str, **extra: Any) -> dict[str, Any]:
    row = {"id": id, "label": label, "demand": demand}
    row.update(extra)
    return row


CATEGORIES: list[dict[str, Any]] = [
    {
        "id": "gui",
        "title": "GUI 桌面",
        "purpose": "窗口程序。点、拖、菜单，不是终端里画的界面。",
        "items": [
            _item("csharp-desktop", "WPF 桌面", "做一个 C# WPF 桌面应用。", work_products=["desktop-app"], language="csharp", purpose="Windows 原生桌面窗口", source="产线 csharp-desktop / .NET 9"),
            _item("csharp-desktop-avalonia", "Avalonia", "做一个 Avalonia 跨平台桌面应用。", work_products=["desktop-app"], language="csharp", body="avalonia", purpose="跨平台桌面 GUI", source="产线 csharp-desktop-avalonia"),
        ],
    },
    {
        "id": "tui",
        "title": "TUI 终端界面",
        "purpose": "在终端里画交互界面，不是命令行参数工具。",
        "items": [
            _item("python-tui", "Python Textual TUI", "做一个 Python TUI。", work_products=["tui"], language="python", purpose="终端全屏交互", source="产线 python-tui / Textual"),
        ],
    },
    {
        "id": "web",
        "title": "Web 前端",
        "purpose": "浏览器里的页面。SPA、SSR、静态站分开，不焊成 fullstack。",
        "items": [
            _item("typescript-web-ui", "Vite 网页", "做一个 TypeScript 前端网页应用。", work_products=["web-ui"], language="typescript", purpose="轻量网页", source="产线 typescript-web-ui / Vite"),
            _item("typescript-web-react", "React SPA", "做一个 React 单页应用。", work_products=["web-spa"], language="typescript", body="react", purpose="React 单页", source="产线 typescript-web-react"),
            _item("typescript-web-vue", "Vue SPA", "做一个 Vue 单页应用。", work_products=["web-spa"], language="typescript", body="vue", purpose="Vue 单页", source="产线 typescript-web-vue"),
            _item("typescript-web-svelte", "Svelte SPA", "做一个 Svelte 单页应用。", work_products=["web-spa"], language="typescript", body="svelte", purpose="Svelte 单页", source="产线 typescript-web-svelte"),
            _item("typescript-web-ssr", "Next.js SSR", "做一个 Next.js 网站。", work_products=["web-ssr"], language="typescript", body="nextjs", purpose="服务端渲染站点", source="产线 typescript-web-ssr"),
            _item("typescript-static-astro", "Astro 静态站", "做一个 Astro 静态站。", work_products=["static-site"], language="typescript", body="astro", purpose="静态内容站", source="产线 typescript-static-astro"),
            _item("python-docs-site", "MkDocs 文档站", "做一个文档站。", work_products=["docs-site"], purpose="项目文档网站", source="产线 python-docs-site"),
            _item("typescript-design-system", "设计系统", "做一个设计系统。", work_products=["design-system"], purpose="可复用 UI 零件库", source="产线 typescript-design-system"),
        ],
    },
    {
        "id": "download",
        "title": "下载 / 网络客户端",
        "purpose": "拉文件、抓页面、调别人的 HTTP。不是自己开一个 API 服务。",
        "items": [
            _item("python-scraper", "爬虫", "做一个爬虫。", work_products=["scraper"], language="python", purpose="抓取网页或接口", source="产线 python-scraper"),
            _item("typescript-generated-sdk", "OpenAPI TS 客户端", "从 OpenAPI 生成 TypeScript 客户端。", work_products=["generated-sdk"], purpose="按合同生成下载/调用 SDK", source="产线 typescript-generated-sdk"),
        ],
    },
    {
        "id": "http",
        "title": "HTTP / 协议服务",
        "purpose": "你对外提供接口。和前端是两个模块，可以组合成双目录。",
        "items": [
            _item("python-http-service", "FastAPI", "做一个 Python 后端服务，提供 HTTP API。", work_products=["http-service"], language="python", purpose="HTTP API", source="产线 python-http-service"),
            _item("csharp-http-service", "ASP.NET", "做一个 ASP.NET Core Web API。", work_products=["http-service"], language="csharp", purpose="HTTP API", source="产线 csharp-http-service"),
            _item("rust-http-service", "Axum", "做一个 Axum HTTP 服务。", work_products=["http-service"], language="rust", body="axum", purpose="Rust HTTP", source="产线 rust-http-service"),
            _item("typescript-http-hono", "Hono", "做一个 Hono 边缘 API。", work_products=["http-service"], language="typescript", body="hono", purpose="边缘 HTTP", source="产线 typescript-http-hono"),
            _item("typescript-http-nest", "NestJS", "做一个 NestJS 微服务。", work_products=["http-service"], language="typescript", body="nestjs", purpose="TS 服务端框架", source="产线 typescript-http-nest"),
            _item("typescript-graphql", "GraphQL", "做一个 GraphQL API。", work_products=["graphql-api"], language="typescript", purpose="GraphQL 接口", source="产线 typescript-graphql"),
            _item("python-grpc", "gRPC", "做一个 gRPC 服务。", work_products=["grpc-service"], purpose="二进制 RPC", source="产线 python-grpc"),
            _item("python-realtime", "WebSocket", "做一个 WebSocket 实时服务。", work_products=["realtime-service"], purpose="长连接推送", source="产线 python-realtime"),
            _item("frontend-backend-split", "FastAPI + React 双目录", "做一个 FastAPI 后端和 React 单页应用。", work_products=["http-service", "web-spa"], language="python", body="react", repo="frontend-backend-split", purpose="一个仓两个包，各自过门", source="装配拓扑 frontend-backend-split，不是焊名全栈 Profile"),
        ],
    },
    {
        "id": "cli-lib",
        "title": "命令行与库",
        "purpose": "CLI 是敲命令；库是给别人 import。不要混成一个 Profile。",
        "items": [
            _item("python-cli", "Python CLI", "做一个 Python 命令行工具。", work_products=["cli"], language="python", purpose="终端命令", source="产线 python-cli"),
            _item("python-cli-typer", "Typer CLI", "做一个带 Typer 的 Python CLI。", work_products=["cli"], language="python", body="typer", purpose="带类型的 CLI", source="产线 python-cli-typer"),
            _item("rust-cli", "Rust clap CLI", "做一个 Rust clap CLI。", work_products=["cli"], language="rust", body="clap", purpose="Rust 命令行", source="产线 rust-cli"),
            _item("typescript-cli", "Commander CLI", "做一个 Commander CLI。", work_products=["cli"], language="typescript", body="commander", purpose="Node 命令行", source="产线 typescript-cli"),
            _item("python-library", "Python 库", "做一个 Python library，提供可复用的文本标准化能力。", work_products=["library"], language="python", purpose="可发布的库", source="产线 python-library"),
            _item("typescript-library", "TypeScript 库", "做一个 TypeScript 库。", work_products=["library"], language="typescript", purpose="TS 包", source="产线 typescript-library"),
            _item("node-library", "Node 库", "做一个 JavaScript library。", work_products=["library"], language="javascript", purpose="JS 包", source="产线 node-library"),
            _item("rust-library", "Rust crate", "做一个 Rust crate，提供可复用的字符串处理能力。", work_products=["library"], language="rust", purpose="crate", source="产线 rust-library"),
            _item("csharp-library", "C# 库", "做一个 C# library，提供可复用的字符串处理能力。", work_products=["library"], language="csharp", purpose="NuGet 库", source="产线 csharp-library"),
        ],
    },
    {
        "id": "desktop-ext",
        "title": "浏览器 / 编辑器扩展",
        "purpose": "挂在别人的壳上，不是独立窗口。",
        "items": [
            _item("browser-extension-js", "JS 浏览器扩展", "做一个 JavaScript 浏览器扩展，必须支持 Chrome 和 Firefox。", work_products=["browser-extension"], language="javascript", purpose="浏览器插件", source="产线 browser-extension-js"),
            _item("browser-extension-wxt", "WXT 扩展", "做一个 TypeScript 浏览器扩展，必须支持 Chrome 和 Firefox。", work_products=["browser-extension"], language="typescript", purpose="TS 浏览器插件", source="产线 browser-extension-wxt"),
            _item("vscode-extension", "VS Code 插件", "做一个 VS Code 插件。", work_products=["vscode-extension"], purpose="编辑器扩展", source="产线 vscode-extension"),
            _item("github-action", "GitHub Action", "做一个 GitHub Action。", work_products=["ci-action"], purpose="CI 步骤", source="产线 github-action"),
        ],
    },
    {
        "id": "data-ml",
        "title": "数据 / 实验 / 模型",
        "purpose": "笔记本、管道、评测、推理。各自一条产线。",
        "items": [
            _item("python-notebook", "笔记本", "做一个 Python Jupyter 研究笔记本。", work_products=["notebook"], language="python", purpose="探索计算", source="产线 python-notebook"),
            _item("python-experiment", "实验仓", "做一个可复现实验仓。", work_products=["experiment"], purpose="固定随机种子的实验", source="产线 python-experiment"),
            _item("python-data-pipeline", "定时 ETL", "做一个定时 ETL。", work_products=["data-pipeline"], purpose="周期性数据处理", source="产线 python-data-pipeline"),
            _item("python-schema-migration", "Alembic 迁移", "做一个独立的数据库 migration 仓库。", work_products=["schema-migration-repo"], purpose="数据库版本", source="产线 python-schema-migration"),
            _item("python-analytics-dbt", "dbt", "做一个 dbt 项目。", work_products=["analytics-transform"], purpose="分析层变换", source="产线 python-analytics-dbt"),
            _item("python-rag", "RAG", "做一个 RAG service。", work_products=["rag-application"], purpose="检索增强问答骨架", source="产线 python-rag"),
            _item("python-model-serving", "模型推理", "做一个模型推理服务。", work_products=["model-serving"], purpose="把模型挂成服务", source="产线 python-model-serving"),
            _item("python-eval-harness", "评测仓", "做一个评测仓。", work_products=["eval-harness"], purpose="离线评测", source="产线 python-eval-harness"),
        ],
    },
    {
        "id": "agent-ops",
        "title": "Agent / 运维 / 云",
        "purpose": "给 Agent 的插头、机器人、函数、容器。工厂自己不当 Host。",
        "items": [
            _item("python-mcp-server", "Python MCP", "做一个 Python MCP 服务器。", work_products=["mcp-server"], language="python", purpose="给 Agent 用的工具插头", source="产线 python-mcp-server"),
            _item("typescript-mcp-server", "TypeScript MCP", "做一个 TypeScript MCP 服务器。", work_products=["mcp-server"], language="typescript", purpose="TS MCP 插头", source="产线 typescript-mcp-server"),
            _item("python-agent-workflow", "Agent 工作流", "做一个用户侧的 agent 工作流项目。", work_products=["agent-workflow"], purpose="编排步骤，不是工厂本体", source="产线 python-agent-workflow"),
            _item("python-bot", "Discord 机器人", "做一个 Discord 机器人。", work_products=["bot"], purpose="聊天机器人", source="产线 python-bot"),
            _item("python-lambda", "AWS Lambda", "做一个 AWS Lambda。", work_products=["serverless-function"], language="python", purpose="短函数", source="产线 python-lambda"),
            _item("cloudflare-worker", "Cloudflare Worker", "做一个 Cloudflare Worker。", work_products=["serverless-function"], language="typescript", purpose="边缘函数", source="产线 cloudflare-worker"),
            _item("python-container-stack", "Compose 栈", "做一个 Docker Compose 栈仓。", work_products=["container-stack"], purpose="多容器编排草稿", source="产线 python-container-stack"),
            _item("python-event-driven", "事件消费者", "做一个纯消费者，没有 HTTP。", work_products=["event-driven-app"], purpose="队列/事件处理", source="产线 python-event-driven"),
            _item("python-observability", "OpenTelemetry 探针", "做一个 OpenTelemetry collector 配置/探针项目。", work_products=["observability-agent"], purpose="可观测配置", source="产线 python-observability"),
            _item("python-schema-contract", "OpenAPI 合同", "做一个 OpenAPI 合同仓。", work_products=["schema-contract"], purpose="只放接口合同", source="产线 python-schema-contract"),
            _item("playwright-test-suite", "Playwright 仓", "做一个独立 Playwright 仓库。", work_products=["test-suite"], purpose="端到端测试仓", source="产线 playwright-test-suite"),
        ],
    },
]

_COMBO_TEMPLATES: list[dict[str, Any]] = [
    {"id": "tpl-fastapi-react", "title": "FastAPI + React", "blurb": "一个仓两个目录，前后端各自过门。", "demand": "做一个 FastAPI 后端和 React 单页应用。", "work_products": ["http-service", "web-spa"], "language": "python", "body": "react", "repo": "frontend-backend-split", "purpose": "双模块装配", "source": "推荐蓝图，不是 fullstack Profile"},
    {"id": "tpl-fastapi-vue", "title": "FastAPI + Vue", "blurb": "后端 FastAPI，前端 Vue，双目录。", "demand": "做一个 FastAPI 后端和 Vue 单页应用。", "work_products": ["http-service", "web-spa"], "language": "python", "body": "vue", "repo": "frontend-backend-split", "purpose": "双模块装配", "source": "推荐蓝图"},
    {"id": "tpl-blank", "title": "空目录", "blurb": "什么都不选，只给你一个空文件夹。", "demand": "", "work_products": [], "blank": True, "purpose": "空白起点", "source": "选配全关"},
]


def _templates() -> list[dict[str, Any]]:
    out = list(_COMBO_TEMPLATES)
    seen = {item["id"] for item in out}
    for category in CATEGORIES:
        for item in category.get("items") or []:
            tid = "tpl-" + str(item.get("id") or "")
            if tid in seen:
                continue
            seen.add(tid)
            out.append(
                {
                    "id": tid,
                    "title": item.get("label") or item.get("id"),
                    "blurb": item.get("purpose") or item.get("demand") or "",
                    "demand": item.get("demand") or "",
                    "work_products": list(item.get("work_products") or []),
                    "language": item.get("language") or "",
                    "body": item.get("body") or "",
                    "repo": item.get("repo") or "single-package",
                    "purpose": item.get("purpose") or "",
                    "source": item.get("source") or "工厂产线",
                }
            )
    return out


TEMPLATES: list[dict[str, Any]] = _templates()

FIELD_OPTIONS = {
    "work_products": [
        {"id": "desktop-app", "label": "desktop-app · GUI 窗口", "group": "界面", "purpose": "操作系统窗口程序", "source": "WPF / Avalonia 产线"},
        {"id": "tui", "label": "tui · 终端界面", "group": "界面", "purpose": "终端全屏交互，不是 CLI", "source": "python-tui / Textual"},
        {"id": "web-ui", "label": "web-ui · 轻量网页", "group": "界面", "purpose": "简单前端页", "source": "Vite 产线"},
        {"id": "web-spa", "label": "web-spa · 单页应用", "group": "界面", "purpose": "React/Vue/Svelte SPA", "source": "对应 body 轮子"},
        {"id": "web-ssr", "label": "web-ssr · 服务端渲染", "group": "界面", "purpose": "Next 一类站点", "source": "typescript-web-ssr"},
        {"id": "static-site", "label": "static-site · 静态站", "group": "界面", "purpose": "构建期出 HTML", "source": "Astro 产线"},
        {"id": "docs-site", "label": "docs-site · 文档站", "group": "界面", "purpose": "文档网站", "source": "MkDocs 产线"},
        {"id": "cli", "label": "cli · 命令行", "group": "接口", "purpose": "argv 命令工具", "source": "python-cli / rust-cli / commander"},
        {"id": "library", "label": "library · 可复用库", "group": "接口", "purpose": "被别人 import/引用", "source": "各语言 library 产线"},
        {"id": "http-service", "label": "http-service · HTTP API", "group": "协议", "purpose": "对外提供 HTTP", "source": "FastAPI / ASP.NET / Axum / Hono / Nest"},
        {"id": "graphql-api", "label": "graphql-api · GraphQL", "group": "协议", "purpose": "GraphQL 接口", "source": "typescript-graphql"},
        {"id": "grpc-service", "label": "grpc-service · gRPC", "group": "协议", "purpose": "二进制 RPC", "source": "python-grpc"},
        {"id": "realtime-service", "label": "realtime-service · WebSocket", "group": "协议", "purpose": "长连接", "source": "python-realtime"},
        {"id": "scraper", "label": "scraper · 下载/爬取", "group": "下载", "purpose": "拉别人的页面或接口", "source": "python-scraper"},
        {"id": "generated-sdk", "label": "generated-sdk · 生成客户端", "group": "下载", "purpose": "按 OpenAPI 生成调用库", "source": "typescript-generated-sdk"},
        {"id": "mcp-server", "label": "mcp-server · Agent 插头", "group": "Agent", "purpose": "给 IDE/Agent 的工具", "source": "python/ts MCP 产线"},
        {"id": "agent-workflow", "label": "agent-workflow · 工作流", "group": "Agent", "purpose": "编排步骤", "source": "python-agent-workflow"},
        {"id": "bot", "label": "bot · 聊天机器人", "group": "Agent", "purpose": "Discord 等", "source": "python-bot"},
        {"id": "browser-extension", "label": "browser-extension · 浏览器扩展", "group": "扩展", "purpose": "Chrome/Firefox 插件", "source": "JS / WXT 产线"},
        {"id": "vscode-extension", "label": "vscode-extension · 编辑器插件", "group": "扩展", "purpose": "VS Code", "source": "vscode-extension"},
        {"id": "ci-action", "label": "ci-action · CI 步骤", "group": "扩展", "purpose": "GitHub Action", "source": "github-action"},
        {"id": "notebook", "label": "notebook · 笔记本", "group": "数据", "purpose": "Jupyter", "source": "python-notebook"},
        {"id": "data-pipeline", "label": "data-pipeline · ETL", "group": "数据", "purpose": "定时处理", "source": "python-data-pipeline"},
        {"id": "schema-migration-repo", "label": "schema-migration-repo · 库表迁移", "group": "数据", "purpose": "Alembic 一类", "source": "python-schema-migration"},
        {"id": "analytics-transform", "label": "analytics-transform · dbt", "group": "数据", "purpose": "分析变换", "source": "python-analytics-dbt"},
        {"id": "rag-application", "label": "rag-application · RAG", "group": "数据", "purpose": "检索增强骨架", "source": "python-rag"},
        {"id": "model-serving", "label": "model-serving · 推理服务", "group": "数据", "purpose": "模型挂服务", "source": "python-model-serving"},
        {"id": "eval-harness", "label": "eval-harness · 评测", "group": "数据", "purpose": "离线评测仓", "source": "python-eval-harness"},
        {"id": "experiment", "label": "experiment · 实验仓", "group": "数据", "purpose": "可复现实验", "source": "python-experiment"},
        {"id": "serverless-function", "label": "serverless-function · 云函数", "group": "运维", "purpose": "Lambda / Worker", "source": "python-lambda / cloudflare-worker"},
        {"id": "container-stack", "label": "container-stack · Compose", "group": "运维", "purpose": "多容器草稿", "source": "python-container-stack"},
        {"id": "event-driven-app", "label": "event-driven-app · 消费者", "group": "运维", "purpose": "无 HTTP 的队列处理", "source": "python-event-driven"},
        {"id": "observability-agent", "label": "observability-agent · 探针", "group": "运维", "purpose": "OTel 配置", "source": "python-observability"},
        {"id": "schema-contract", "label": "schema-contract · 接口合同", "group": "运维", "purpose": "只放 OpenAPI", "source": "python-schema-contract"},
        {"id": "test-suite", "label": "test-suite · 独立测试仓", "group": "运维", "purpose": "Playwright 等", "source": "playwright-test-suite"},
        {"id": "design-system", "label": "design-system · 设计系统", "group": "界面", "purpose": "可复用 UI 零件", "source": "typescript-design-system"},
    ],
    "languages": [
        {"id": "python", "label": "Python", "purpose": "脚本、服务、数据、Agent", "source": "CPython ≥3.11 + 工厂钉死 uv 0.10.0"},
        {"id": "typescript", "label": "TypeScript", "purpose": "前端、Node、扩展", "source": "工厂钉死 npm 10.9.2，不用系统 npm 11"},
        {"id": "javascript", "label": "JavaScript", "purpose": "无 TS 的前端/扩展", "source": "同一把 npm 机床"},
        {"id": "rust", "label": "Rust", "purpose": "crate / clap / axum", "source": "cargo 1.98.0"},
        {"id": "csharp", "label": "C#", "purpose": "桌面、库、ASP.NET", "source": "dotnet 9.0.315"},
    ],
    "bodies": [
        {"id": "", "label": "（不指定车身）", "purpose": "只用语言默认骨架，不再套一个具体框架。", "source": "Profile 默认 recipe"},
        {"id": "typer", "label": "typer · Python CLI 框架", "purpose": "把命令行参数变成有类型的子命令。", "source": "开源 Typer，挂在 python-cli-typer 产线"},
        {"id": "react", "label": "react · 浏览器 GUI", "purpose": "网页里画组件，不是桌面窗口。", "source": "开源 React 18.3.1，挂在 typescript-web-react"},
        {"id": "vue", "label": "vue · 浏览器 GUI", "purpose": "网页组件框架。", "source": "开源 Vue，挂在 typescript-web-vue"},
        {"id": "svelte", "label": "svelte · 浏览器 GUI", "purpose": "编译期组件框架。", "source": "开源 Svelte，挂在 typescript-web-svelte"},
        {"id": "nextjs", "label": "nextjs · SSR 网站", "purpose": "服务端渲染的 React 站点。", "source": "开源 Next 15.2.4"},
        {"id": "hono", "label": "hono · 边缘 HTTP", "purpose": "跑在 Worker/边缘的小 HTTP 框架。", "source": "开源 Hono"},
        {"id": "nestjs", "label": "nestjs · TS 服务端", "purpose": "TypeScript 的服务端框架。", "source": "开源 NestJS"},
        {"id": "axum", "label": "axum · Rust HTTP", "purpose": "Rust 异步 HTTP。", "source": "开源 Axum"},
        {"id": "clap", "label": "clap · Rust CLI", "purpose": "Rust 命令行参数。", "source": "开源 clap"},
        {"id": "avalonia", "label": "avalonia · 跨平台桌面 GUI", "purpose": "窗口程序，不是网页。", "source": "开源 Avalonia"},
        {"id": "commander", "label": "commander · Node CLI", "purpose": "Node 命令行。", "source": "开源 Commander"},
        {"id": "astro", "label": "astro · 静态站", "purpose": "构建期出 HTML。", "source": "开源 Astro"},
        {"id": "textual", "label": "textual · 终端 GUI", "purpose": "在终端里画界面，不是 argv CLI。", "source": "开源 Textual，挂在 python-tui"},
    ],
    "quality": [
        {"id": "security", "label": "security · 安全", "purpose": "默认不当儿戏，密钥不进仓", "source": "质量属性"},
        {"id": "testability", "label": "testability · 可测", "purpose": "要能跑测试", "source": "质量属性"},
        {"id": "reliability", "label": "reliability · 可靠", "purpose": "错误要可见", "source": "质量属性"},
        {"id": "performance", "label": "performance · 性能", "purpose": "有性能约束时再选", "source": "质量属性"},
        {"id": "privacy", "label": "privacy · 隐私", "purpose": "少留用户数据", "source": "质量属性"},
    ],
    "targets": [
        {"id": "windows", "label": "windows", "purpose": "在 Windows 上跑", "source": "目标平台"},
        {"id": "linux", "label": "linux", "purpose": "在 Linux 上跑", "source": "目标平台"},
        {"id": "macos", "label": "macos", "purpose": "在 macOS 上跑", "source": "目标平台"},
        {"id": "browser", "label": "browser", "purpose": "在浏览器里跑", "source": "目标平台"},
        {"id": "node", "label": "node", "purpose": "在 Node 里跑", "source": "目标平台"},
    ],
    "lifecycle": [
        {"id": "prototype", "label": "prototype · 原型", "purpose": "先能跑", "source": "生命周期"},
        {"id": "development", "label": "development · 开发", "purpose": "还在长功能", "source": "生命周期"},
        {"id": "production", "label": "production · 生产", "purpose": "要当正式产品", "source": "生命周期"},
    ],
    "scale": [
        {"id": "small", "label": "small · 小", "purpose": "一个人几天", "source": "规模提示"},
        {"id": "medium", "label": "medium · 中", "purpose": "一个小团队", "source": "规模提示"},
        {"id": "large", "label": "large · 大", "purpose": "只作提示，工厂仍只给骨架", "source": "规模提示"},
    ],
    "constraints": [
        {"id": "no-electron", "label": "不用 Electron/Tauri", "purpose": "工厂不产这两类壳", "source": "宪法硬约束"},
        {"id": "no-network-in-ci", "label": "CI 不许出网", "purpose": "验证门尽量离线", "source": "硬约束"},
        {"id": "native-repo", "label": "原生仓结构", "purpose": "按该语言习惯布局", "source": "工厂承诺"},
        {"id": "empty-if-all-off", "label": "全关则空目录", "purpose": "选配全关合法", "source": "装配选项"},
    ],
    "preferred": [
        {"id": "uv", "label": "uv", "purpose": "Python 机床", "source": "工厂钉 0.10.0"},
        {"id": "npm", "label": "npm", "purpose": "JS 机床", "source": "工厂钉 10.9.2"},
        {"id": "cargo", "label": "cargo", "purpose": "Rust 机床", "source": "工厂钉 1.98.0"},
        {"id": "dotnet", "label": "dotnet", "purpose": "C# 机床", "source": "工厂钉 9.0.315"},
    ],
    "prohibited": [
        {"id": "electron", "label": "electron", "purpose": "不走这条壳", "source": "禁止技术"},
        {"id": "tauri", "label": "tauri", "purpose": "不走这条壳", "source": "禁止技术"},
        {"id": "latest", "label": "latest 自动晋升", "purpose": "看见新版本不等于支持", "source": "兼容性门"},
    ],
}

OSS_MODULES: list[dict[str, Any]] = [
    {"id": "textual", "kind": "pypi", "group": "TUI", "label": "Textual", "purpose": "Python 终端 GUI", "source": "https://pypi.org/project/textual/", "url": "https://pypi.org/pypi/textual/json"},
    {"id": "wpf-ui", "kind": "nuget", "group": "GUI", "label": "WPF-UI", "purpose": "WinUI 风格 WPF 控件", "source": "https://www.nuget.org/packages/WPF-UI", "url": "https://api.nuget.org/v3-flatcontainer/wpf-ui/index.json"},
    {"id": "avalonia", "kind": "nuget", "group": "GUI", "label": "Avalonia", "purpose": "跨平台桌面 GUI", "source": "https://www.nuget.org/packages/Avalonia", "url": "https://api.nuget.org/v3-flatcontainer/avalonia/index.json"},
    {"id": "react", "kind": "npm", "group": "Web GUI", "label": "React", "purpose": "浏览器组件", "source": "https://www.npmjs.com/package/react", "url": "https://registry.npmjs.org/react"},
    {"id": "vue", "kind": "npm", "group": "Web GUI", "label": "Vue", "purpose": "浏览器组件", "source": "https://www.npmjs.com/package/vue", "url": "https://registry.npmjs.org/vue"},
    {"id": "svelte", "kind": "npm", "group": "Web GUI", "label": "Svelte", "purpose": "浏览器组件", "source": "https://www.npmjs.com/package/svelte", "url": "https://registry.npmjs.org/svelte"},
    {"id": "vite", "kind": "npm", "group": "Web 机床", "label": "Vite", "purpose": "前端打包机床", "source": "https://www.npmjs.com/package/vite", "url": "https://registry.npmjs.org/vite"},
    {"id": "playwright", "kind": "npm", "group": "测试", "label": "Playwright", "purpose": "浏览器端到端", "source": "https://www.npmjs.com/package/playwright", "url": "https://registry.npmjs.org/playwright"},
    {"id": "fastapi", "kind": "pypi", "group": "HTTP", "label": "FastAPI", "purpose": "Python HTTP API", "source": "https://pypi.org/project/fastapi/", "url": "https://pypi.org/pypi/fastapi/json"},
    {"id": "httpx", "kind": "pypi", "group": "下载", "label": "httpx", "purpose": "Python HTTP 客户端", "source": "https://pypi.org/project/httpx/", "url": "https://pypi.org/pypi/httpx/json"},
    {"id": "typer", "kind": "pypi", "group": "CLI", "label": "Typer", "purpose": "Python CLI", "source": "https://pypi.org/project/typer/", "url": "https://pypi.org/pypi/typer/json"},
    {"id": "mcp", "kind": "pypi", "group": "Agent", "label": "mcp", "purpose": "Python MCP SDK", "source": "https://pypi.org/project/mcp/", "url": "https://pypi.org/pypi/mcp/json"},
    {"id": "hono", "kind": "npm", "group": "HTTP", "label": "Hono", "purpose": "边缘 HTTP", "source": "https://www.npmjs.com/package/hono", "url": "https://registry.npmjs.org/hono"},
    {"id": "axum", "kind": "crate", "group": "HTTP", "label": "axum", "purpose": "Rust HTTP", "source": "https://crates.io/crates/axum", "url": "https://crates.io/api/v1/crates/axum"},
    {"id": "clap", "kind": "crate", "group": "CLI", "label": "clap", "purpose": "Rust CLI", "source": "https://crates.io/crates/clap", "url": "https://crates.io/api/v1/crates/clap"},
    {"id": "next", "kind": "npm", "group": "Web SSR", "label": "Next.js", "purpose": "React SSR", "source": "https://www.npmjs.com/package/next", "url": "https://registry.npmjs.org/next"},
    {"id": "astro", "kind": "npm", "group": "静态站", "label": "Astro", "purpose": "内容站", "source": "https://www.npmjs.com/package/astro", "url": "https://registry.npmjs.org/astro"},
]

AI_PRESETS = [
    {"id": "spacexai", "label": "SpaceXAI / xAI（推荐）", "endpoint": "https://api.x.ai/v1/chat/completions", "model": "grok-4.5", "key_env": "XAI_API_KEY"},
    {"id": "openai", "label": "OpenAI", "endpoint": "https://api.openai.com/v1/chat/completions", "model": "gpt-4o-mini", "key_env": "OPENAI_API_KEY"},
    {"id": "groq", "label": "Groq", "endpoint": "https://api.groq.com/openai/v1/chat/completions", "model": "llama-3.3-70b-versatile", "key_env": "GROQ_API_KEY"},
    {"id": "deepseek", "label": "DeepSeek", "endpoint": "https://api.deepseek.com/chat/completions", "model": "deepseek-chat", "key_env": "DEEPSEEK_API_KEY"},
    {"id": "ollama", "label": "Ollama（本机已安装模型）", "endpoint": "http://127.0.0.1:11434", "model": "", "key_env": "", "note": "不写死模型名。点「读取本机模型」只列出 ollama list 里已有的，不会替你 pull。"},
]


def _factory_lines() -> list[dict[str, Any]]:
    rows = []
    for category in CATEGORIES:
        for item in category.get("items") or []:
            rows.append(
                {
                    **item,
                    "group": category.get("title") or category.get("id"),
                    "kind": "factory-line",
                    "status": "owned",
                    "purpose": item.get("purpose") or item.get("demand") or "",
                    "source": item.get("source") or f"产线 {item.get('id')}",
                }
            )
    return rows


def _merge_user_modules(field_options: dict[str, Any], extra: list[dict[str, Any]]) -> dict[str, Any]:
    merged = {key: list(value) for key, value in field_options.items()}
    bodies = merged.setdefault("bodies", [])
    known = {str(item.get("id")) for item in bodies}
    for item in extra:
        body_id = str(item.get("body") or item.get("id") or "").strip()
        if not body_id or body_id in known:
            continue
        if item.get("kind") in {"factory-line", "pypi", "npm", "crate", "nuget", "url", "file", "yaml"} or item.get("status") == "preloaded":
            bodies.append(
                {
                    "id": body_id,
                    "label": f"{item.get('label') or body_id} · 仓库资源",
                    "purpose": item.get("purpose") or "用户仓库里的开源功能模块",
                    "source": item.get("source") or "user warehouse",
                }
            )
            known.add(body_id)
    return merged


def catalog(extra_modules: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    extras = list(extra_modules or [])
    fields = _merge_user_modules(FIELD_OPTIONS, extras)
    # T06：数据驱动门禁——用内核 registry 真实产线标注可用性，不硬编码业务清单。
    try:
        from availability import annotate_catalog

        annotated_fields, body_compatibility = annotate_catalog(fields)
    except Exception:
        # fail-safe：可用性计算异常时退回原 field_options，不影响现有行为
        annotated_fields, body_compatibility = fields, {}
    modules = [*OSS_MODULES]
    seen = {str(item.get("id")) for item in modules}
    for item in extras:
        mid = str(item.get("id") or "")
        if mid and mid not in seen:
            modules.append(item)
            seen.add(mid)
    return {
        "schema": "project-factory-gui-catalog/3",
        "categories": CATEGORIES,
        "templates": _templates(),
        "field_options": annotated_fields,
        "body_compatibility": body_compatibility,
        "work_products": [item["id"] for item in fields["work_products"]],
        "languages": [item["id"] for item in fields["languages"]],
        "bodies": [item["id"] for item in fields["bodies"]],
        "modules": modules,
        "factory_lines": _factory_lines(),
        "ai_presets": AI_PRESETS,
        "options": [
            {"id": "scaffold", "label": "生成语言根车架", "default": True, "purpose": "写出该语言的项目骨架", "source": "AssemblyOptions.scaffold"},
            {"id": "verification", "label": "跑验证门", "default": True, "purpose": "机械验证，不是感觉", "source": "AssemblyOptions.verification"},
            {"id": "overlay", "label": "写入 Factory overlay / skill", "default": True, "purpose": "给后续 Agent 的纪律", "source": "AssemblyOptions.overlay"},
            {"id": "harness", "label": "写入 AGENTS.md / CLAUDE.md", "default": True, "purpose": "Agent 适配，可关", "source": "AssemblyOptions.harness"},
            {"id": "readme", "label": "写入 README", "default": True, "purpose": "给人看的入口", "source": "AssemblyOptions.readme"},
        ],
    }
