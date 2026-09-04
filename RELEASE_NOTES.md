# Release Notes — Project Factory 0.14.30 · UX5.1 Fluent

首个公开发行版（Windows 桌面）。

## 新增

- **UX5.1 Fluent 桌面壳**（WPF / .NET 9，WPF-UI 4.3.0）：FluentWindow / Mica / NavigationView。
- **Factory Core 0.14.30**（`project-factory-blueprint-kernel`）：human-first CLI、evidence-first 生成、验证套件、恢复与就地升级。
- **常驻 Python Bridge**：`backend\project_factory_bridge.py` 以 JSON-line 协议为桌面壳提供响应式核心服务。
- **NSIS 安装器**：按当前用户安装，无需管理员权限；携带钉死的 npm/uv 工具链。
- **隔离 Python Core 运行时**：不修改系统 Python（依赖：`jsonschema`、`PyYAML`）。

## 修复

- 开源仓库测试套件全绿（此前依赖被 gitignore 的内部夹具，现已改由 golden 自动重建）。
- 安装器脚本适配 net9.0-windows 目标与项目实际目录结构。

## 已知限制

- 需要 64 位 Python 3.11+ 作为 venv 基础。
- 生成项目的验证状态取决于本机工具链（缺工具链的项目为 `PARTIALLY_VERIFIED`）。

> 完整变更见 `CHANGELOG.md`。