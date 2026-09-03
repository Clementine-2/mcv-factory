# Project Factory Quickstart

## 1. See whether the Factory is ready

```bash
project-factory status
```

For deeper diagnosis without keeping a generated project:

```bash
project-factory status --deep
```

`READY_WITH_WARNINGS` is normal when optional Codex/Claude/Spec Kit/Dagu runtimes are absent. Optional runtime absence must remain visible; it is not a local scaffolding failure.

## 2. Create a project

```bash
project-factory new my-project "做一个 Python 命令行工具，不能覆盖输入文件。"
```

The default output root is `./out`. Use `--out PATH` when a different destination is needed. Existing paths/ZIPs are not silently overwritten.

## 3. Check the extracted project

```bash
project-factory check ./out/my-project
```

`check` is read-only and validates Factory-owned integrity/contracts without executing the generated project's runtime commands.

## 4. Verify the portable ZIP

```bash
project-factory verify ./out/my-project.zip
```

`verify` restores into a temporary directory and runs the required verification spine. The temporary restore is separate from the user's output tree.

## 5. Open it in a coding Harness

The generated `AGENTS.md` / `CLAUDE.md` are adapters over `.project/contract/agent-contract.md`. Harness installation/authentication/availability is separate from project generation and must not be inferred from files being present.

## 6. Upgrade later

```bash
project-factory upgrade plan ./out/my-project
```

Inspect the DryRun, then apply only with its exact plan hash. Factory upgrade owns the Factory overlay, not normal business source files.

## 7. Recover a Factory checkpoint

```bash
project-factory checkpoint inspect checkpoint.zip
project-factory checkpoint plan checkpoint.zip --out-dir ./restore-new
project-factory checkpoint restore checkpoint.zip --out-dir ./restore-new --confirm-plan-sha256 <plan-hash>
```

Restore refuses an existing destination and does not auto-delete a partial recovery directory.

## Advanced / machine commands

The older explicit command surface remains available (`generate`, `restore-verify`, `doctor`, `normalize`, `validate`, `runner`, `extension`, and others). Use `--json` on human commands when structured output is desired.
