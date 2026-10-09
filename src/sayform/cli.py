"""Command-line entry point `say` (spec/13-tooling.md section 1).

Milestone M0/M1 provides `say --version`. Commands land milestone by milestone
(see the status table in README.md); until then they report exit 2 with a clear message.
"""

from __future__ import annotations

import argparse
import sys

from . import CORE_VERSION, EDITION, SPEC_VERSION, __version__

COMMANDS = ("run", "check", "fmt", "explain", "test", "hash", "core", "repl")


def version_text() -> str:
    return f"say {__version__} (spec {SPEC_VERSION}, edition {EDITION}, {CORE_VERSION})"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="say", description="Sayform reference interpreter.")
    ap.add_argument("--version", action="store_true", help="print version and exit")
    ap.add_argument("command", nargs="?", choices=COMMANDS)
    ap.add_argument("args", nargs=argparse.REMAINDER)
    ns = ap.parse_args(argv)
    if ns.version:
        print(version_text())
        return 0
    if ns.command is None:
        ap.print_help()
        return 0
    print(
        f"say {ns.command}: not available in {__version__} yet (see README status table).",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
