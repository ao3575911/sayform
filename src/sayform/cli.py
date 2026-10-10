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
from typing import Any

from . import CORE_VERSION, EDITION, SPEC_VERSION, __version__
from .diagnostics import SayError, Sink

COMMANDS = ("run", "check", "fmt", "explain", "test", "hash", "core", "repl")


def version_text() -> str:
    return f"say {__version__} (spec {SPEC_VERSION}, edition {EDITION}, {CORE_VERSION})"


def load(path: str, sink: Sink | None = None) -> tuple[str, Any, list[Any]]:
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
        out = print_module(mod, surface, comments)
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
        defs, mh = hash_module(mod)
        print(f"{show_hash(mh)}  {mod.name}")
        if ns.defs:
            for name, h in sorted(defs.items()):
                print(f"{show_hash(h)}  {mod.name}.{name}")
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


def run_file(
    path: str, write: Any = None, allow: set[str] | None = None, deny: set[str] | None = None, shuffle: Any = None
) -> int:
    """`say run`: exit 0 ok, 1 main returned a problem, 2 compile error, 4 refused, 70 panic."""
    from .diagnostics import EXIT
    from .evaluator import program
    from .values import Problem

    def out(text: str, end: str = "\n") -> None:
        sys.stdout.write(text + end)

    try:
        _, mod, _ = load(path)
        policy = deny or set()
        ev, result = big_stack(
            lambda: program(
                mod, write or out, read_line, lambda e: e not in policy and e != "network", real=True, shuffle=shuffle
            )
        )
        for w in ev.warnings:
            print(w.render(), file=sys.stderr)
    except SayError as e:
        e.diag.file = e.diag.file or path
        report(e, path, False)
        return EXIT[e.diag.severity]
    except RecursionError:
        print("panic[SAY-E0212]: call depth limit reached", file=sys.stderr)
        return 70
    if isinstance(result, Problem):
        print(f"problem[{result.kind.name}]: main returned a problem", file=sys.stderr)
        print(f" what: {result.message or result.kind.name}", file=sys.stderr)
        print("  why: `main` gave back a problem instead of finishing normally.", file=sys.stderr)
        print("  try: Handle it with `try`, `or else` or `match` before it reaches `main`.", file=sys.stderr)
        return 1
    return 0


def read_line() -> str | None:
    line = sys.stdin.readline()
    return line.rstrip("\n") if line else None


def big_stack(fn: Any) -> Any:
    """Run `fn` in a thread with a large stack so deep Sayform recursion cannot crash the host."""
    import threading

    box: dict[str, Any] = {}

    def target() -> None:
        try:
            box["value"] = fn()
        except BaseException as e:  # re-raised in the caller
            box["error"] = e

    sys.setrecursionlimit(200_000)
    threading.stack_size(512 * 1024 * 1024)
    t = threading.Thread(target=target)
    t.start()
    t.join()
    if "error" in box:
        raise box["error"]
    return box["value"]


def cmd_run(ns: argparse.Namespace) -> int:
    try:
        return run_file(ns.file, deny=set(ns.deny or ()), shuffle=ns.shuffle_tasks)
    except Exception as e:  # internal fault: never show a Python traceback (prompt section 9)
        print(f"internal error: {type(e).__name__}: {e}\nThis is a bug in say; please report it.", file=sys.stderr)
        return 70


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
    p = sub.add_parser("run", help="run a program's main")
    p.add_argument("file")
    p.add_argument("--deny", action="append", help="refuse an effect (host policy)")
    p.add_argument("--shuffle-tasks", type=int, metavar="SEED", help="perturb the task ready queue deterministically")
    p.add_argument("args", nargs="*", help="program arguments after `--`")
    for name in ("check", "explain", "test", "repl"):
        p = sub.add_parser(name)
        p.add_argument("args", nargs=argparse.REMAINDER)
    ns = ap.parse_args(argv)
    if ns.version:
        print(version_text())
        return 0
    handler = {"fmt": cmd_fmt, "hash": cmd_hash, "core": cmd_core, "run": cmd_run}.get(ns.command or "")
    if handler is not None:
        return handler(ns)
    if ns.command is None:
        ap.print_help()
        return 0
    print(f"say {ns.command}: not available in {__version__} yet (see README status table).", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
