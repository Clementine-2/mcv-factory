"""Native Rust library crate on the cargo language root.

This is a library profile, not a Python extension. Maturin/PyO3 is a different
kind (native-extension) and stays observed until that line is owned.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..recipes import ProviderView, RecipeError, ScaffoldResult, run_command

_CRATE = re.compile(r"^[a-z][a-z0-9-]*$")


def rust_crate_name(project_name: str) -> str:
    value = project_name.casefold().replace("_", "-")
    if not _CRATE.fullmatch(value):
        raise RecipeError(f"Project name {project_name!r} cannot map to a safe Cargo crate name.")
    return value


def rust_ident(crate_name: str) -> str:
    return crate_name.replace("-", "_")


def _render_lib(ident: str) -> str:
    return f'''/// 返回脚手架就绪状态文本。
pub fn scaffold_status() -> &'static str {{
    "{ident} scaffold ready"
}}

/// 示例函数：向指定名字打招呼。
pub fn greet(name: &str) -> String {{
    format!("你好，{{name}}！")
}}

/// 示例函数：判断字符串是否为回文（忽略空白与大小写，空串不算回文）。
pub fn is_palindrome(value: &str) -> bool {{
    let normalized: String = value
        .chars()
        .filter(|c| !c.is_whitespace())
        .flat_map(char::to_lowercase)
        .collect();
    let reversed: String = normalized.chars().rev().collect();
    !normalized.is_empty() && normalized == reversed
}}

/// 示例函数：统计按空白分隔的单词数量。
pub fn word_count(value: &str) -> usize {{
    value.split_whitespace().count()
}}

#[cfg(test)]
mod tests {{
    use super::*;

    #[test]
    fn status_is_defined() {{
        assert_eq!(scaffold_status(), "{ident} scaffold ready");
    }}

    #[test]
    fn greet_builds_hello_message() {{
        assert_eq!(greet("世界"), "你好，世界！");
    }}

    #[test]
    fn is_palindrome_detects_mirror_strings() {{
        assert!(is_palindrome("abcba"));
        assert!(is_palindrome("Racecar"));
        assert!(!is_palindrome("hello"));
        assert!(!is_palindrome(""));
    }}

    #[test]
    fn word_count_counts_tokens() {{
        assert_eq!(word_count(" one  two three "), 3);
        assert_eq!(word_count(""), 0);
    }}
}}
'''


def _patch_cargo_toml(path: Path, *, crate_name: str, ident: str, purpose: str) -> None:
    description = json.dumps(purpose, ensure_ascii=False)
    path.write_text(
        f"""[package]
name = {json.dumps(crate_name)}
version = "0.1.0"
edition = "2021"
description = {description}
publish = false

[lib]
name = {json.dumps(ident)}
""",
        encoding="utf-8",
    )


def scaffold_cargo_lib(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "cargo-lib":
        raise RecipeError(f"Unsupported Cargo scaffold recipe: {recipe}")
    crate_name = rust_crate_name(project_name)
    ident = rust_ident(crate_name)
    scaffold = run_command(
        [
            provider.executable,
            "new",
            "--lib",
            "--vcs",
            "none",
            "--name",
            crate_name,
            str(project_root),
        ],
        staging_root,
    )
    _patch_cargo_toml(project_root / "Cargo.toml", crate_name=crate_name, ident=ident, purpose=purpose)
    src = project_root / "src"
    src.mkdir(parents=True, exist_ok=True)
    (src / "lib.rs").write_text(_render_lib(ident), encoding="utf-8")
    return ScaffoldResult(
        command_result=scaffold,
        layout={
            "source": "src/lib.rs",
            "packaging": "Cargo.toml",
        },
    )
