from __future__ import annotations

from ..verification import ClaimSpec, GateSpec, ProviderView, VerificationSuite, _command_gate


def build_csharp_http_service_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    executable = provider.executable
    gates = (
        _command_gate(
            "aspnet-tests",
            "generated ASP.NET in-process health tests",
            [executable, "test", "tests", "--nologo", "--disable-build-servers"],
        ),
        GateSpec(
            "aspnet-artifacts",
            "compiled ASP.NET service artifacts",
            "artifact",
            artifact_patterns=("bin/Debug/net9.0/*.dll", "tests/bin/Debug/net9.0/*.dll"),
            min_artifacts=1,
        ),
    )
    claims = (
        ClaimSpec(
            "health-endpoint",
            "The /health endpoint responds in-process via WebApplicationFactory.",
            "local generated scaffold",
            ("aspnet-tests", "aspnet-artifacts"),
        ),
        ClaimSpec(
            "live-http",
            "The service accepts traffic on a bound HTTP port.",
            "external HTTP listener",
            (),
            True,
            "Kestrel was not bound to a port by this suite.",
        ),
    )
    return VerificationSuite(
        "csharp-http-service",
        "0.1",
        "generated ASP.NET Core HTTP service scaffold",
        gates,
        claims,
        "dotnet",
        (
            "This is a minimal ASP.NET Core service, not a full-stack template.",
            "A bound Kestrel process is not a verification gate.",
            "Public deployment and TLS are outside this verification scope.",
        ),
    )
