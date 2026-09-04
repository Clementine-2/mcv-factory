# UX5.1 Design Notes — Project Factory Fluent Shell

## 架构

```
WPF Shell (FluentWindow / Mica / NavigationView)
        │   JSON-line 协议（按 id 匹配）
        ▼
Python Backend (backend\project_factory_bridge.py，常驻进程)
        │
        ▼
Factory Core (project_factory_blueprint_kernel，隔离 .pf_runtime venv)
        normalize → reason → generate → verify → recover
```

## 关键取舍

- **常驻 bridge 取代"每次调子进程"**：消除 UI 卡顿，请求/响应按行 JSON 与唯一 `id` 配对。
- **Core 完全隔离**：自带 venv，绝不改动系统 Python；依赖仅 `jsonschema` + `PyYAML`。
- **AI 辅助是可选、"人优先"**：只通过 API Key 的**环境变量名**接入；文本外发前做密钥脱敏
  （`sk-…`、`ghp_…`、`AKIA…`、`Bearer …`、`api_key=…` 等）；任何情况下不把密钥写入磁盘。
- **证据优先（evidence-first）**：每个生成项目的每个断言都有对应工件，`UNVERIFIED` 就如实标注。

## 安装布局（%LOCALAPPDATA%\Programs\ProjectFactory）

| 目录 | 内容 |
|---|---|
| `app\` | WPF 桌面壳（ProjectFactory.exe / factory.exe 等价入口） |
| `backend\` | Python bridge（project_factory_bridge.py、network_ops.py） |
| `wheel\` | Factory Core wheel（project_factory_blueprint_kernel） |
| `tools\` | 钉死的 npm1092 / uv010 工具链（版本校验契约） |
| `.pf_runtime\` | 隔离 Python Core venv（bootstrap_windows.py 准备） |
| `installer\` | 本次安装对应的安装器源码与关闭进程脚本 |

卸载**保留** `%LOCALAPPDATA%\ProjectFactory` 下的用户设置与项目资产。