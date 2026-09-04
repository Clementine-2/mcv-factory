# MCV Factory（基地车工厂）

**语言：** [English](README.md) · **简体中文** · [繁體中文](README.zh-Hant.md)

> ⚠️ **正在积极开发中** — 界面与接口可能随时调整，暂不建议用于生产环境。

> 一款 Windows 桌面「项目工厂」：把高层级需求变成经过验证、有证据支撑的软件项目。
> 前端是 Fluent/WPF，后端是隔离的 Python「工厂内核」（Factory Core），负责生成、验证与恢复工程脚手架。

MCV Factory（基地车工厂）得名于《命令与征服：红色警戒》里的基地车 MCV（代码中代号 Project Factory），是一款**以人为本**的工具：CLI / UI 负责收集意图，内核负责产出项目蓝图，而关于生成项目的每一条声明都有证据产物背书，而不是空口断言。

- **工厂内核版本：** `0.14.30`
- **界面壳：** UX5.1 — Windows 11 Fluent（WPF / .NET，WPF-UI 4.3.0）
- **许可证：** [MIT](./LICENSE)

---

## 目录

- [这是什么](#这是什么)
- [架构](#架构)
- [仓库结构](#仓库结构)
- [环境要求](#环境要求)
- [构建与运行（Windows）](#构建与运行windows)
- [Python 桥接](#python-桥接)
- [安全模型](#安全模型)
- [贡献](#贡献)
- [许可证](#许可证)

---

## 这是什么

MCV Factory 接收一条需求（自由文本或引导式表单），对它进行语义推理，然后产出工程脚手架与一组**验证声明**。每条声明都会对照真实产物校验；任何看起来像密钥的内容，在持久化或发送到外部服务之前都会被统一脱敏。

两个部分协同工作：

1. **工厂内核**（`core/`）— 一个 Python 内核（`project-factory-blueprint-kernel`），负责需求归一化、语义推理、蓝图生成、验证套件与失败恢复，通过 JSON 桥被调用。
2. **用户界面壳**（`shell/` + `backend/`）— 一个自包含的 Windows WPF 应用（FluentWindow、Mica、NavigationView），通过常驻的 Python 后端进程与内核通信。

---

## 架构

```
┌─────────────────────────────┐      JSON over stdin/stdout        ┌──────────────────────────────┐
│  WPF Shell (shell/)         │ ───────────────────────────────▶  │  Python backend (backend/)    │
│  FluentWindow / Mica / NV   │      line-delimited `id` match     │  resident process bridge      │
└─────────────────────────────┘ ◀───────────────────────────────  └───────────────┬──────────────┘
                                                                                   │ invokes
                                                                                   ▼
                                                                          ┌────────────────────────────┐
                                                                          │  Factory Core (core/src)    │
                                                                          │  normalize → reason →       │
                                                                          │  generate → verify → recover│
                                                                          └────────────────────────────┘
```

- 界面壳启动**一个**常驻 Python 进程，按行交换 JSON 请求/响应，用每行唯一的 `id` 匹配。这一设计取代了旧的「每次调用都拉起子进程」的模型，消除了界面卡顿。
- 内核完全隔离：运行在独立的 venv 中，绝不改动系统 Python。可选 AI 辅助只读取**环境变量名**对应的凭据，永不把实际值写入磁盘。

---

## 仓库结构

```
ProjectFactory/
├── core/                     # 工厂内核（Python kernel）
│   ├── pyproject.toml        # project-factory-blueprint-kernel 0.14.30
│   ├── requirements.txt      # jsonschema==4.26.0, PyYAML==6.0.3
│   ├── src/project_factory/  # kernel source (package = src layout)
│   ├── tests/                # test suite
│   ├── docs/ schemas/ scripts/ fixtures/ golden_outputs/ compatibility/
├── shell/                    # WPF / .NET 桌面客户端（ProjectFactory.Workbench）
│   ├── App.xaml(.cs) MainWindow.xaml(.cs) app.manifest
│   ├── Models/ Services/ Views/ Assets/
│   └── ProjectFactory.Workbench.csproj
├── backend/                  # Python 桥接层（由界面壳驱动）
│   └── project_factory_bridge.py (availability, gui_catalog, module_store, …)
├── installer/                # NSIS 3.12 安装包源码（BUILD_INSTALLER.*, *.nsi）
├── tools/                    # QA / 生命周期验证脚本
├── factory_resources/        # 资源宇宙（YAML / Markdown 目录）
├── bootstrap_windows.py      # Windows 首次运行引导
├── hot_upgrade_launch.py     # 原地升级 / 启动助手
├── THIRD_PARTY_NOTICES.md    # 第三方许可证汇总
├── LICENSE                   # MIT
├── README.md  CONTRIBUTING.md  SECURITY.md  CODE_OF_CONDUCT.md  .gitignore
```

---

## 环境要求

桌面版面向 **Windows 10 / 11**。

| 组件             | 版本               | 说明                                            |
|------------------|--------------------|-------------------------------------------------|
| .NET SDK         | 9.0.x（固定）        | 用于构建/发布 WPF 壳（目标框架 `net9.0-windows`）   |
| WPF-UI (NuGet)   | 4.3.0（固定）        | Fluent 控件；构建时由 NuGet 拉取                  |
| Python           | 64 位 3.11+        | 仅用于创建隔离的 Core venv                        |
| NSIS             | 3.12（Modern UI 2） | 仅构建安装包时需要                                 |

Python 运行时依赖（安装到隔离 venv，绝不装入系统环境）：

```
jsonschema==4.26.0
PyYAML==6.0.3
```

---

## 构建与运行（Windows）

### 1. 工厂内核（Python）

```powershell
cd core
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
# 冒烟测试：
.\.venv\Scripts\python -m project_factory --help
```

### 2. WPF 界面壳

```powershell
cd shell
dotnet build -c Release
# 或生成自包含、可移植的构建：
dotnet publish -c Release -r win-x64 --self-contained true -o publish_win64
```

### 3. 桥接与启动

界面壳期望 Python 后端位于已安装应用旁边。本地运行时，`bootstrap_windows.py` 负责准备隔离的 Core venv；`hot_upgrade_launch.py` 负责原地升级/启动。`installer/` 下的安装器源码会生成一个按用户安装的 `ProjectFactory` 程序（位于 `%LOCALAPPDATA%\Programs\ProjectFactory`）。

> 编排完整 Windows 安装包构建的公开脚本位于 `installer/`（NSIS）。它们会在使用前按哈希校验固定的工具链归档。

---

## Python 桥接

`backend/project_factory_bridge.py` 是一个**常驻**进程：界面壳每行写一条 JSON 请求（每条带唯一 `id`），并按 `id` 读取对应响应。这保证了界面响应流畅，也避免了每次操作都重新启动一个 Python 解释器。

请求示例（一行）：

```json
{"id": 1, "action": "status"}
```

---

## 安全模型

- **不硬编码任何密钥。** API Key / Token 只通过**环境变量名**读取；内核绝不把实际值写入磁盘。
- **密钥脱敏。** 在持久化或发送文本到任何外部服务之前，内核会脱敏凭据内容（`sk-…`、`ghp_…`、`AKIA…`、`Bearer …`、`api_key=…` 等）。见 `core/src/project_factory/normalizer.py`。
- **隔离运行。** 内核运行在独立 venv 中，不触碰系统 Python 包。
- 生成的工程模板使用仅限开发环境的默认值（例如脚手架 `docker-compose` 中的示例 `POSTGRES_PASSWORD: app`）——这只是教学示例，不是 MCV Factory 自身的凭据。

漏洞请按 [SECURITY.md](./SECURITY.md) 报告。

---

## 贡献

感谢你的关注！开发环境搭建、测试运行方式与 PR 流程见 [CONTRIBUTING.md](./CONTRIBUTING.md)。参与贡献即表示你同意你的贡献按 MIT 许可证授权。

---

## 许可证

以 [MIT 许可证](./LICENSE) 发布。