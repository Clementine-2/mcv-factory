# 欢迎使用 基地车生产厂

基地车生产厂是一个把"一句话需求"变成"可验证工程脚手架"的桌面工具：

- **WPF / .NET 桌面壳**：Windows 11 Fluent 风格（`app\ProjectFactory.exe` 或等价的 `app\factory.exe`）。
- **隔离 Python Core**：首次启动/安装时通过 `bootstrap_windows.py` 在程序目录 `.pf_runtime` 下准备隔离的 Python 运行时，不污染系统 Python。
- **一切验证皆有证据**：生成的项目带有 `project.lock.json`、`.project/evidence/*` 等证据文件，可复查、可升级、可回滚。

## 快速开始

1. 双击 `基地车生产厂.lnk`（或运行 `%LOCALAPPDATA%\Programs\ProjectFactory\app\ProjectFactory.exe`）。
2. 在输入框描述你的项目（例如"做一个 Python 命令行工具，批量读取目录里的 JSON 并转换格式"）。
3. 选择配置文件（可选）与 AI 辅助（可选，API Key 只读取环境变量名，永不落盘）。
4. 点击生成，Factory Core 会产出工程目录 + 验证证据。

## 常见问题

- **启动提示找不到 Python**：需要 64 位 Python 3.11+。安装后运行"修复 Python Core 运行时"（开始菜单）即可。
- **生成结果依赖外部工具链**（Node/npm、uv、cargo、dotnet 等）：Factory 会检测本机版本并如实标注验证状态，缺工具的项目会是 `PARTIALLY_VERIFIED`。

详细文档见仓库根 `README.md`；安全说明见 `SECURITY.md`。