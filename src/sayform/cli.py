"""Command-line entry point `say` (spec/13-tooling.md section 1).

Commands land milestone by milestone (see the status table in README.md); a command that
is not available yet reports exit 2 with a clear message.
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

from . import CORE_VERSION, EDITION, SPEC_VERSION, __version__
from .diagnostics import SayError, Sink

COMMANDS = ("run", "check", "fmt", "explain", "test", "hash", "core", "repl")


def version_text() -> str:
    return f"say {__version__} (spec {SPEC_VERSION}, edition {EDITION}, {CORE_VERSION})"


def load(path: str, sink: Sink | None = None) -> tuple[str, object, list[object]]:
    from .lexer import lex
    from .parser import parse

    text = Path(path).read_text(encoding="utf-8")
    name = Path(path).stem
    return text, parse(text, path, sink, name=name), list(lex(text).comments)


def report(e: SayError, path: str, as_json: bool) -> int:
    if as_json:
        print(json.dumps({"version": "say-json/1", "diagnostics": [e.diag.to_json()]}), file=sys.stderr)
    else:
        src = Path(path).read_text(encoding="utf-8") if Path(path).exists() else None
        print(e.diag.render(src), file=sys.stderr)
    return 2


def cmd_fmt(ns: argparse.Namespace) -> int:
    from .parser import parse
    from .printer import print_module

    surface = "symbols" if ns.symbols else "words"
    status = 0
    for path in ns.paths:
        try:
            text, mod, comments = load(path)
        except SayError as e:
            return report(e, path, ns.json)
        out = print_module(mod, surface, comments)  # type: ignore[arg-type]
        if parse(out, path, name=Path(path).stem) != mod:
            print(f"say fmt: internal error: reprinting {path} changes its core (SAY-E1001)", file=sys.stderr)
            return 2
        if ns.check:
            if out != text:
                sys.stdout.writelines(difflib.unified_diff(text.splitlines(True), out.splitlines(True), path, path))
                status = 1
        elif out != text:
            Path(path).write_text(out, encoding="utf-8")
    return status


def cmd_hash(ns: argparse.Namespace) -> int:
    from .scs import hash_module, show_hash

    for path in ns.paths:
        try:
            _, mod, _ = load(path)
        except SayError as e:
            return report(e, path, ns.json)
        defs, mh = hash_module(mod)  # type: ignore[arg-type]
        print(f"{show_hash(mh)}  {mod.name}")  # type: ignore[attr-defined]
        if ns.defs:
            for name, h in sorted(defs.items()):
                print(f"{show_hash(h)}  {mod.name}.{name}")  # type: ignore[attr-defined]
    return 0


def cmd_core(ns: argparse.Namespace) -> int:
    from .scs import to_json

    try:
        _, mod, _ = load(ns.file)
    except SayError as e:
        return report(e, ns.file, ns.json)
    if ns.json:
        print(json.dumps({"version": "say-json/1", "core": to_json(mod)}, indent=1, ensure_ascii=False))
    else:
        print(mod)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="say", description="Sayform reference interpreter.")
    ap.add_argument("--version", action="store_true", help="print version and exit")
    sub = ap.add_subparsers(dest="command")
    p = sub.add_parser("fmt", help="normalise source files")
    p.add_argument("paths", nargs="+")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--words", action="store_true")
    g.add_argument("--symbols", action="store_true")
    p.add_argument("--unicode", action="store_true")
    p.add_argument("--check", action="store_true")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("hash", help="print core hashes")
    p.add_argument("paths", nargs="+")
    p.add_argument("--defs", action="store_true")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("core", help="print the core tree")
    p.add_argument("file")
    p.add_argument("--json", action="store_true")
    for name in ("run", "check", "explain", "test", "repl"):
        p = sub.add_parser(name)
        p.add_argument("args", nargs=argparse.REMAINDER)
    ns = ap.parse_args(argv)
    if ns.version:
        print(version_text())
        return 0
    handler = {"fmt": cmd_fmt, "hash": cmd_hash, "core": cmd_core}.get(ns.command or "")
    if handler is not None:
        return handler(ns)
    if ns.command is None:
        ap.print_help()
        return 0
    print(f"say {ns.command}: not available in {__version__} yet (see README status table).", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
