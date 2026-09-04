# Verification

## 构建验证（本发行版）

- **Factory Core（Python）**：`python -m pytest core/tests -q` 全量通过（366 passed / 12 skipped / 93 subtests），
  跳过项均为"本机未安装对应工具链"（maturin、php、godot、flutter 等），非失败。
- **WPF Shell（.NET）**：`dotnet build shell/ProjectFactory.Workbench.csproj -c Release` 0 警告 0 错误。
- **安装器**：NSIS 3.12 编译通过，安装后 `%LOCALAPPDATA%\Programs\ProjectFactory\app\ProjectFactory.exe`
  可启动并唤起隔离 Python Core（`.pf_runtime`）。

## 设计上的验证保证（生成项目侧）

- 每个生成项目携带 `project.lock.json` 与 `.project/evidence/*`（generation-verification、harness/host/process 兼容性等）。
- 升级路径：`plan_upgrade`（DryRun 只读）→ `apply_upgrade`（生成回滚点）→ `rollback_upgrade`（精确还原字节）。
- 未执行或部分验证的项在证据中如实标记为 `UNVERIFIED` / `PARTIALLY_VERIFIED`，不虚报。

> 本文件为公开发行版自检说明；仓库内不含内部 QA 流程的凭证或路径。