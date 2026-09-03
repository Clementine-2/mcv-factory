from __future__ import annotations

from ..verification import (
    ClaimSpec,
    GateSpec,
    ProviderView,
    VerificationSuite,
    _command_gate,
    _python_package_name,
)


def build_python_rag_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    package_name = _python_package_name(project_name)
    executable = provider.executable
    gates = (
        _command_gate(
            "rag-imports",
            "generated RAG import",
            [
                executable,
                "--offline",
                "run",
                "python",
                "-c",
                f"from {package_name}.rag import scaffold_status; print(scaffold_status())",
            ],
            "rag scaffold ready",
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
        ClaimSpec("rag-importable", "The generated RAG module imports locally.", "local generated scaffold", ("rag-imports",)),
        ClaimSpec("retrieve-ok", "The retriever returns the fixture document.", "local generated scaffold", ("unit-tests",)),
        ClaimSpec("package-builds", "The generated scaffold builds a wheel and source distribution locally.", "local package build", ("package-build", "package-artifacts")),
        ClaimSpec(
            "vector-runtime",
            "A live vector database and embedding model were queried.",
            "external retrieval runtime",
            (),
            True,
            "No embeddings API or vector DB was launched.",
        ),
    )
    return VerificationSuite(
        "python-rag",
        "0.1",
        "generated in-memory RAG scaffold",
        gates,
        claims,
        "python",
        ("This is an in-memory fixture retriever, not a hosted vector DB.",),
    )
