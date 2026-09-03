from __future__ import annotations

from ..verification import (
    ClaimSpec,
    GateSpec,
    ProviderView,
    VerificationSuite,
    _command_gate,
    _python_package_name,
)


def build_python_event_driven_suite(project_name: str, provider: ProviderView) -> VerificationSuite:
    package_name = _python_package_name(project_name)
    executable = provider.executable
    gates = (
        _command_gate(
            "worker-imports",
            "generated event consumer import",
            [
                executable,
                "--offline",
                "run",
                "python",
                "-c",
                f"from {package_name}.worker import scaffold_status; print(scaffold_status())",
            ],
            "event consumer scaffold ready",
        ),
        _command_gate(
            "unit-tests",
            "in-process consumer tests",
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
        ClaimSpec("worker-importable", "The generated event consumer imports locally.", "local generated scaffold", ("worker-imports",)),
        ClaimSpec("handle-ok", "handle() processes a queued message in-process.", "local generated scaffold", ("unit-tests",)),
        ClaimSpec("package-builds", "The generated scaffold builds a wheel and source distribution locally.", "local package build", ("package-build", "package-artifacts")),
        ClaimSpec(
            "broker-runtime",
            "The consumer read from a live Kafka/RabbitMQ/SQS broker.",
            "external message broker",
            (),
            True,
            "No broker was launched. This is a pure in-process consumer, not an HTTP service with a side queue.",
        ),
    )
    return VerificationSuite(
        "python-event-driven",
        "0.1",
        "generated in-process event consumer scaffold",
        gates,
        claims,
        "python",
        (
            "This is a pure consumer. HTTP + Celery remains http-service.",
            "Kafka and other brokers are outside this verification scope.",
        ),
    )
