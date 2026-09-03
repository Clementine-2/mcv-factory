from __future__ import annotations

from ..verification import (
    ClaimSpec,
    GateSpec,
    ProviderView,
    VerificationSuite,
    _command_gate,
    _python_package_name,
)


def build_python_agent_workflow_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    package_name = _python_package_name(project_name)
    executable = provider.executable
    gates = (
        _command_gate(
            "workflow-imports",
            "generated workflow import",
            [
                executable,
                "--offline",
                "run",
                "python",
                "-c",
                f"from {package_name}.workflow import scaffold_status; print(scaffold_status())",
            ],
            "agent workflow scaffold ready",
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
        ClaimSpec("workflow-importable", "The generated workflow imports locally.", "local generated scaffold", ("workflow-imports",)),
        ClaimSpec("step-runs", "The local workflow graph echoes a payload.", "local generated scaffold", ("unit-tests",)),
        ClaimSpec("package-builds", "The generated scaffold builds a wheel and source distribution locally.", "local package build", ("package-build", "package-artifacts")),
        ClaimSpec(
            "llm-runtime",
            "A live LLM completed the workflow.",
            "external LLM runtime",
            (),
            True,
            "No model provider was called. This is a user-project workflow, not the factory brain.",
        ),
    )
    return VerificationSuite(
        "python-agent-workflow",
        "0.1",
        "generated local agent-workflow scaffold",
        gates,
        claims,
        "python",
        (
            "LangChain/Pydantic AI are user-project libraries, not factory kernel.",
            "Live LLM calls are outside this verification scope.",
        ),
    )
