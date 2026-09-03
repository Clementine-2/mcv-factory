from __future__ import annotations

from ..verification import ClaimSpec, GateSpec, ProviderView, VerificationSuite, _command_gate


def build_cloudflare_worker_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "npm-ci-offline",
            "offline npm install from lockfile",
            [executable, "ci", "--offline", "--no-fund", "--no-audit"],
        ),
        _command_gate("unit-tests", "local Worker module tests", [executable, "test"]),
        GateSpec(
            "worker-artifacts",
            "worker module and wrangler drawing",
            "artifact",
            artifact_patterns=("src/index.js", "wrangler.toml"),
            min_artifacts=2,
        ),
    )
    claims = (
        ClaimSpec("tests-pass", "The generated Worker module tests pass locally.", "local generated scaffold", ("unit-tests",)),
        ClaimSpec("worker-drawing", "The wrangler.toml drawing and worker module exist.", "local generated scaffold", ("worker-artifacts",)),
        ClaimSpec(
            "cloudflare-runtime",
            "The worker ran on Cloudflare's edge.",
            "Cloudflare Workers runtime",
            (),
            True,
            "wrangler deploy was not launched by this suite.",
        ),
    )
    return VerificationSuite(
        "cloudflare-worker",
        "0.1",
        "generated Cloudflare Worker scaffold",
        gates,
        claims,
        "node",
        (
            "wrangler deploy and Cloudflare account login are not verification gates.",
            "The factory does not install wrangler as a required runtime.",
        ),
    )
