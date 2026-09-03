"""Axum HTTP service on the cargo language root.

Binding a port is not a verification gate. tokio/net is not enabled: this
Windows GNU host cannot compile windows-sys (dlltool missing).
"""

from __future__ import annotations

import json
from pathlib import Path

from ..recipes import ProviderView, RecipeError, ScaffoldResult, run_command
from .cargo_lib import rust_crate_name, rust_ident

AXUM_PIN = "0.8.4"
TOWER_PIN = "0.5.2"
FUTURES_EXECUTOR_PIN = "0.3.31"


def _render_lib(ident: str) -> str:
    return f'''use axum::{{routing::get, Json, Router}};
use serde::Serialize;

#[derive(Serialize)]
pub struct Health {{
    pub status: &'static str,
    pub service: &'static str,
}}

pub fn app() -> Router {{
    Router::new().route("/health", get(health))
}}

async fn health() -> Json<Health> {{
    Json(Health {{ status: "ok", service: "{ident}" }})
}}

#[cfg(test)]
mod tests {{
    use super::*;
    use axum::body::Body;
    use axum::http::{{Request, StatusCode}};
    use tower::ServiceExt;

    #[test]
    fn health_returns_ok() {{
        let response = futures_executor::block_on(async {{
            app()
                .oneshot(Request::builder().uri("/health").body(Body::empty()).unwrap())
                .await
                .unwrap()
        }});
        assert_eq!(response.status(), StatusCode::OK);
    }}
}}
'''


def _render_main(ident: str) -> str:
    return f'''use {ident}::app;

fn main() {{
    let _ = app();
    println!("Project scaffold ready. Binding a TCP port is not a factory verification gate.");
}}
'''


def scaffold_cargo_axum(
    recipe: str,
    provider: ProviderView,
    project_name: str,
    project_root: Path,
    staging_root: Path,
    purpose: str,
) -> ScaffoldResult:
    if recipe != "cargo-axum":
        raise RecipeError(f"Unsupported Axum scaffold recipe: {recipe}")
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
        [provider.executable, "add", f"axum@={AXUM_PIN}", "--no-default-features", "--features", "json"],
        project_root,
        timeout=600,
    )
    run_command(
        [provider.executable, "add", f"tower@={TOWER_PIN}", "--features", "util"],
        project_root,
        timeout=600,
    )
    run_command([provider.executable, "add", "serde@=1.0.217", "--features", "derive"], project_root, timeout=600)
    run_command(
        [provider.executable, "add", "--dev", f"futures-executor@={FUTURES_EXECUTOR_PIN}"],
        project_root,
        timeout=600,
    )
    run_command([provider.executable, "fetch"], project_root, timeout=600)
    return ScaffoldResult(
        command_result=scaffold,
        layout={"source": "src/", "packaging": "Cargo.toml"},
    )
