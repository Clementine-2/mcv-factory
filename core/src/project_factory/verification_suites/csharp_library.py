from __future__ import annotations

from ..verification import ClaimSpec, GateSpec, ProviderView, VerificationSuite, _command_gate


def build_csharp_library_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "classlib-tests",
            "generated C# library unit tests",
            [executable, "test", "tests", "--nologo", "--disable-build-servers"],
        ),
        _command_gate(
            "classlib-pack",
            "local nupkg pack",
            [executable, "pack", "--nologo", "--disable-build-servers"],
        ),
        GateSpec(
            "classlib-artifacts",
            "compiled library and nupkg artifacts",
            "artifact",
            artifact_patterns=("bin/Debug/*.nupkg", "bin/Debug/net9.0/*.dll", "tests/bin/Debug/net9.0/*.dll"),
            min_artifacts=1,
        ),
    )
    claims = (
        ClaimSpec(
            "library-tests-pass",
            "The generated C# library unit tests pass locally.",
            "local generated scaffold",
            ("classlib-tests",),
        ),
        ClaimSpec(
            "library-packs",
            "The generated class library packs a nupkg locally.",
            "local generated scaffold",
            ("classlib-pack", "classlib-artifacts"),
        ),
        ClaimSpec(
            "nuget-publish",
            "The package is published to nuget.org.",
            "public registry publication",
            (),
            True,
            "nuget.org publication is outside this verification scope.",
        ),
    )
    return VerificationSuite(
        "csharp-library",
        "0.1",
        "generated C# class library scaffold",
        gates,
        claims,
        "dotnet",
        (
            "This is a class library, not a WPF or ASP.NET project.",
            "Public nuget.org publication is outside this verification scope.",
        ),
    )
