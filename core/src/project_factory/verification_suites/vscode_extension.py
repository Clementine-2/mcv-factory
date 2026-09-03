from __future__ import annotations

from ..verification import ClaimSpec, GateSpec, ProviderView, VerificationSuite, _command_gate


def build_vscode_extension_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "npm-ci-offline",
            "offline npm install from lockfile",
            [executable, "ci", "--offline", "--no-fund", "--no-audit"],
        ),
        _command_gate("unit-tests", "local VS Code extension smoke tests", [executable, "test"]),
        _command_gate("vsix-package", "vsce package", [executable, "run", "package"]),
        GateSpec("vsix-artifact", "packaged VSIX", "artifact", artifact_patterns=("*.vsix",), min_artifacts=1),
    )
    claims = (
        ClaimSpec("tests-pass", "The generated VS Code extension smoke tests pass locally.", "local generated scaffold", ("unit-tests",)),
        ClaimSpec("vsix-builds", "vsce can produce a VSIX locally.", "local package build", ("vsix-package", "vsix-artifact")),
        ClaimSpec(
            "vscode-runtime",
            "The extension was loaded in a real VS Code instance.",
            "VS Code runtime",
            (),
            True,
            "VS Code was not launched by this suite.",
        ),
        ClaimSpec(
            "marketplace-publish",
            "The extension is published to the Visual Studio Marketplace.",
            "public marketplace",
            (),
            True,
            "Marketplace publication is outside this verification scope.",
        ),
    )
    return VerificationSuite(
        "vscode-extension",
        "0.1",
        "generated VS Code extension scaffold",
        gates,
        claims,
        "node",
        (
            "VSIX packaging is verified; a live VS Code host was not launched.",
            "Marketplace publication is outside this verification scope.",
        ),
    )
