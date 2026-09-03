from __future__ import annotations

from ..verification import (
    ClaimSpec,
    GateSpec,
    ProviderView,
    VerificationSuite,
    _command_gate,
    _python_package_name,
)


def build_python_mcp_server_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    package_name = _python_package_name(project_name)
    executable = provider.executable
    gates = (
        _command_gate(
            "server-imports",
            "generated MCP server import",
            [
                executable,
                "--offline",
                "run",
                "python",
                "-c",
                f"from {package_name}.server import mcp; print('mcp server scaffold ready')",
            ],
            "mcp server scaffold ready",
        ),
        _command_gate(
            "unit-tests",
            "local unit tests",
            [executable, "--offline", "run", "python", "-m", "unittest", "discover", "-s", "tests", "-v"],
        ),
        _command_gate("package-build", "local Python package build", [executable, "--offline", "build"]),
        GateSpec(
            "package-artifacts",
            "wheel and source distribution artifacts",
            "artifact",
            artifact_patterns=("dist/*.whl", "dist/*.tar.gz"),
            min_artifacts=2,
        ),
    )
    claims = (
        ClaimSpec(
            "server-importable",
            "The generated MCP server module imports locally.",
            "local generated scaffold",
            ("server-imports",),
        ),
        ClaimSpec(
            "in-memory-tools",
            "The generated MCP tools are callable through the official in-memory client.",
            "local generated scaffold",
            ("unit-tests",),
        ),
        ClaimSpec(
            "package-builds",
            "The generated scaffold builds a wheel and source distribution locally.",
            "local package build",
            ("package-build", "package-artifacts"),
        ),
        ClaimSpec(
            "live-host",
            "The server works when launched by a real MCP host.",
            "external MCP host",
            (),
            True,
            "Inspector and desktop hosts were not launched by this suite. mcp dev is a development tool, not a verification gate.",
        ),
    )
    return VerificationSuite(
        "python-mcp-server",
        "0.1",
        "generated Python MCP server scaffold",
        gates,
        claims,
        "python",
        (
            "Public PyPI publication is outside this verification scope.",
            "mcp dev / MCP Inspector is a development tool and is not a VERIFIED gate.",
            "The Factory generates MCP servers; it is not an MCP Host.",
        ),
    )
