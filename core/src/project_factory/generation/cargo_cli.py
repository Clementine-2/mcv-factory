"""Clap CLI on the cargo language root. argparse-style Python CLI stays the default Python line."""

from __future__ import annotations

import json
from pathlib import Path

from ..recipes import ProviderView, RecipeError, ScaffoldResult, run_command
from .cargo_lib import rust_crate_name, rust_ident

CLAP_PIN = "4.5.32"


def _render_lib(ident: str) -> str:
    return f'''use clap::Parser;

#[derive(Parser, Debug)]
#[command(name = "{ident}", version = "0.1.0", about = "{ident} scaffold ready")]
pub struct Cli {{}}

pub fn scaffold_status() -> &'static str {{
    "{ident} scaffold ready"
}}

pub fn run() {{
    let _ = Cli::parse();
    println!("Project scaffold ready. Implement domain behavior through the coding-agent workflow.");
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
}}
'''


def _render_main(ident: str) -> str:
    return f"fn main() {{\n    {ident}::run();\n}}\n"


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
