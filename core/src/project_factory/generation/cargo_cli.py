"""Clap CLI on the cargo language root. argparse-style Python CLI stays the default Python line."""

from __future__ import annotations

import json
from pathlib import Path

from ..recipes import ProviderView, RecipeError, ScaffoldResult, run_command
from .cargo_lib import rust_crate_name, rust_ident

CLAP_PIN = "4.5.32"


def _render_lib(ident: str) -> str:
    return f'''use clap::{{Parser, Subcommand}};

/// 示例 CLI：演示 greet 与 add 两个子命令。
#[derive(Parser, Debug)]
#[command(name = "{ident}", version = "0.1.0", about = "{ident} scaffold ready")]
pub struct Cli {{
    #[command(subcommand)]
    pub command: Command,
}}

#[derive(Subcommand, Debug)]
pub enum Command {{
    /// 向某人打招呼
    Greet {{
        /// 打招呼的对象名字
        name: String,
    }},
    /// 计算两个整数的和
    Add {{
        a: i32,
        b: i32,
    }},
}}

/// 返回脚手架就绪状态文本。
pub fn scaffold_status() -> &'static str {{
    "{ident} scaffold ready"
}}

/// 示例逻辑：拼接打招呼文本。
pub fn greet(name: &str) -> String {{
    format!("你好，{{name}}！")
}}

/// 示例逻辑：计算两数之和。
pub fn add(a: i32, b: i32) -> i32 {{
    a + b
}}

pub fn run() {{
    let cli = Cli::parse();
    match cli.command {{
        Command::Greet {{ name }} => println!("{{}}", greet(&name)),
        Command::Add {{ a, b }} => println!("{{}}", add(a, b)),
    }}
}}

#[cfg(test)]
mod tests {{
    use super::*;
    use clap::Parser;

    #[test]
    fn status_is_defined() {{
        assert_eq!(scaffold_status(), "{ident} scaffold ready");
    }}

    #[test]
    fn version_flag_is_defined() {{
        let err = Cli::try_parse_from(["{ident}", "--version"]).unwrap_err();
        assert!(err.to_string().contains("0.1.0"), "{{err}}");
    }}

    #[test]
    fn greet_builds_message() {{
        assert_eq!(greet("世界"), "你好，世界！");
    }}

    #[test]
    fn add_sums_arguments() {{
        assert_eq!(add(2, 3), 5);
        assert_eq!(add(-1, 1), 0);
    }}

    #[test]
    fn parses_greet_subcommand() {{
        let cli = Cli::try_parse_from(["{ident}", "greet", "张三"]).unwrap();
        match cli.command {{
            Command::Greet {{ name }} => assert_eq!(name, "张三"),
            _ => panic!("expected greet subcommand"),
        }}
    }}

    #[test]
    fn parses_add_subcommand() {{
        let cli = Cli::try_parse_from(["{ident}", "add", "4", "5"]).unwrap();
        match cli.command {{
            Command::Add {{ a, b }} => {{
                assert_eq!(a, 4);
                assert_eq!(b, 5);
            }}
            _ => panic!("expected add subcommand"),
        }}
    }}
}}
'''


def _render_main(ident: str) -> str:
    return f"fn main() {{\n    {ident}::run();\n}}\n"


def _render_cli_test(crate_name: str) -> str:
    return f'''// 通过 std::process 直接调用编译出的二进制，验证真实 CLI 行为。
// Cargo 为集成测试注入 CARGO_BIN_EXE_<bin名>（连字符原样保留）。
use std::process::Command;

fn bin() -> Command {{
    Command::new(env!("CARGO_BIN_EXE_{crate_name}"))
}}

#[test]
fn greet_subcommand_prints_greeting() {{
    let output = bin().args(["greet", "世界"]).output().expect("运行 greet 子命令失败");
    assert!(output.status.success());
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert_eq!(stdout.trim(), "你好，世界！");
}}

#[test]
fn add_subcommand_prints_sum() {{
    let output = bin().args(["add", "2", "3"]).output().expect("运行 add 子命令失败");
    assert!(output.status.success());
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert_eq!(stdout.trim(), "5");
}}

#[test]
fn version_flag_reports_version() {{
    let output = bin().arg("--version").output().expect("运行 --version 失败");
    assert!(output.status.success());
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(stdout.contains("0.1.0"));
}}
'''


def scaffold_cargo_cli(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "cargo-cli":
        raise RecipeError(f"Unsupported Cargo CLI scaffold recipe: {recipe}")
    crate_name = rust_crate_name(project_name)
    ident = rust_ident(crate_name)
    scaffold = run_command(
        [provider.executable, "new", "--bin", "--vcs", "none", "--name", crate_name, str(project_root)],
        staging_root,
    )
    description = json.dumps(purpose, ensure_ascii=False)
    (project_root / "Cargo.toml").write_text(
        f"""[package]
name = {json.dumps(crate_name)}
version = "0.1.0"
edition = "2021"
description = {description}
publish = false

[lib]
name = {json.dumps(ident)}
path = "src/lib.rs"

[[bin]]
name = {json.dumps(crate_name)}
path = "src/main.rs"
""",
        encoding="utf-8",
    )
    src = project_root / "src"
    src.mkdir(parents=True, exist_ok=True)
    (src / "lib.rs").write_text(_render_lib(ident), encoding="utf-8")
    (src / "main.rs").write_text(_render_main(ident), encoding="utf-8")
    tests_dir = project_root / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "cli.rs").write_text(_render_cli_test(crate_name), encoding="utf-8")
    run_command(
        [
            provider.executable,
            "add",
            f"clap@={CLAP_PIN}",
            "--no-default-features",
            "--features",
            "derive,std,help,usage,error-context",
        ],
        project_root,
        timeout=600,
    )
    run_command([provider.executable, "fetch"], project_root, timeout=600)
    return ScaffoldResult(
        command_result=scaffold,
        layout={"source": "src/", "packaging": "Cargo.toml"},
    )
