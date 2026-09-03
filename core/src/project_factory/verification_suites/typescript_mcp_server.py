from __future__ import annotations

from ..verification import ClaimSpec, GateSpec, ProviderView, VerificationSuite, _command_gate


def build_typescript_mcp_server_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "npm-ci-offline",
            "offline npm install from lockfile",
            [executable, "ci", "--offline", "--no-fund", "--no-audit"],
        ),
        _command_gate("unit-tests", "in-memory MCP client tests", [executable, "test"]),
        GateSpec(
            "server-artifacts",
            "compiled MCP server entry",
            "artifact",
            artifact_patterns=("dist/server.js",),
            min_artifacts=1,
        ),
    )
    claims = (
        ClaimSpec("tests-pass", "The generated MCP server in-memory client tests pass locally.", "local generated scaffold", ("unit-tests",)),
        ClaimSpec("server-builds", "The TypeScript MCP server compiles locally.", "local package build", ("server-artifacts",)),
        ClaimSpec(
            "live-host",
            "The server works when launched by a real MCP host.",
            "external MCP host",
            (),
            True,
            "Inspector and desktop hosts were not launched by this suite.",
        ),
    )
    return VerificationSuite(
        "typescript-mcp-server",
        "0.1",
        "generated TypeScript MCP server scaffold",
        gates,
        claims,
        "node",
        (
            "The Factory generates MCP servers; it is not an MCP Host.",
            "stdio live hosts are not a verification gate.",
        ),
    )
