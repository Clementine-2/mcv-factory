from __future__ import annotations

import sys

# CI / fresh Windows consoles may default to cp1252, which cannot encode
# characters such as ``∞`` in FACTORY_STAGE. Force UTF-8 output with a
# lossless fallback so the CLI never crashes on *printable* output.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except (OSError, ValueError):
            pass

from .factory import main as factory_main
from .decision import main as decision_main
from .semantic import main as semantic_main
from .normalizer import main as normalize_main
from .compatibility import main as compatibility_main
from .upgrade import main as upgrade_main
from .extensions import main as extension_main
from .host import main as host_main
from .runner import main as runner_main
from .validator import main as validate_main
from .product import main as product_main
from .recovery import main as recovery_main
from .ux import main as ux_main
from .factory import FACTORY_STAGE, FACTORY_VERSION


def main() -> int:
    argv = sys.argv[1:]
    if not argv or argv[0] in {"-h", "--help", "help", "status", "new", "check", "verify", "template"}:
        routed = [] if not argv or argv[0] == "help" else argv
        return ux_main(routed)
    if argv and argv[0] in {"--version", "version"}:
        print(f"Project Factory {FACTORY_VERSION} ({FACTORY_STAGE})")
        return 0
    if argv and argv[0] in {"doctor", "bootstrap"}:
        return product_main(argv)
    if argv and argv[0] == "checkpoint":
        return recovery_main(argv[1:])
    if argv and argv[0] == "normalize":
        return normalize_main(argv[1:])
    if argv and argv[0] == "intake":
        return semantic_main(argv[1:])
    if argv and argv[0] == "decide":
        return decision_main(argv[1:])
    if argv and argv[0] == "validate":
        return validate_main(argv[1:])
    if argv and argv[0] == "compatibility":
        return compatibility_main(argv[1:])
    if argv and argv[0] == "upgrade":
        return upgrade_main(argv[1:])
    if argv and argv[0] == "extension":
        return extension_main(argv[1:])
    if argv and argv[0] == "host":
        return host_main(argv[1:])
    if argv and argv[0] == "runner":
        return runner_main(argv[1:])
    if argv and argv[0] in {"generate", "restore-verify"}:
        return factory_main(argv)
    # Backward compatible with P1.2/P1: blueprint path as the first argument means validate.
    return validate_main(argv)


raise SystemExit(main())
