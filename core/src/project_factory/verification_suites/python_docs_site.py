from __future__ import annotations

from ..verification import ClaimSpec, GateSpec, ProviderView, VerificationSuite, _command_gate


def build_python_docs_site_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "mkdocs-build",
            "MkDocs production build",
            [executable, "--offline", "run", "mkdocs", "build", "--strict"],
        ),
        GateSpec(
            "docs-artifacts",
            "built documentation site",
            "artifact",
            artifact_patterns=("site/index.html",),
            min_artifacts=1,
        ),
    )
    claims = (
        ClaimSpec("docs-build", "MkDocs can produce a static site locally.", "local generated scaffold", ("mkdocs-build", "docs-artifacts")),
        ClaimSpec(
            "docs-serve",
            "The docs site was served and browsed.",
            "local HTTP preview",
            (),
            True,
            "mkdocs serve was not launched by this suite.",
        ),
    )
    return VerificationSuite(
        "python-docs-site",
        "0.1",
        "generated MkDocs documentation site scaffold",
        gates,
        claims,
        "python",
        (
            "mkdocs serve is a development preview and is not a verification gate.",
            "Observed latest MkDocs/Material is not auto-promoted; this line is pinned.",
        ),
    )
