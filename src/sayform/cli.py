"""Command-line entry point `say` (spec/13-tooling.md section 1).

Commands land milestone by milestone (see the status table in README.md); a command that
is not available yet reports exit 2 with a clear message.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path
from typing import Any

from . import CORE_VERSION, EDITION, SPEC_VERSION, __version__
from . import core as C
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
        from .modules import load_tree

        mod, deps = load_tree(path)
        policy = deny or set()
        ev, result = big_stack(
            lambda: program(
                mod,
                write or out,
                read_line,
                lambda e: e not in policy and e != "network",
                real=True,
                shuffle=shuffle,
                deps=tuple(deps),
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


def cmd_explain(ns: argparse.Namespace) -> int:
    from .explain import explain

    path, _, at = ns.file.partition(":") if not Path(ns.file).exists() else (ns.file, "", "")
    try:
        _, mod, _ = load(path)
    except SayError as e:
        return report(e, path, ns.json)
    lines = explain(mod, int(at) if at else None)
    print(json.dumps({"version": "say-json/1", "explanation": lines}) if ns.json else "\n".join(lines))
    return 0


def note_examples(text: str) -> str:
    """Note `example:` lines become checks (spec 13 section 5.3); malformed ones are SAY-E1005."""
    out = []
    for i, ln in enumerate(text.splitlines(), 1):
        m = re.match(r"\s+example:\s*(.*)$", ln)
        if not m:
            continue
        call, gives, value = m.group(1).rpartition(" gives ")
        if gives:
            out.append(f"check that ({call}) equals ({value.rstrip('.')})")
            continue
        call, fails, kind = m.group(1).rpartition(" fails with ")
        if not fails or not call:
            raise SayError("E1005", i, at_line=i)
        out.append(f"check that ({call}) fails with {kind.rstrip('.')}")
    return "\n\n" + "\n".join(out) + "\n" if out else ""


def test_files(paths: list[str]) -> list[str]:
    out: list[str] = []
    for p in paths:
        q = Path(p)
        out += sorted(str(x) for x in q.rglob("*.say")) if q.is_dir() else [p]
    return out


def cmd_test(ns: argparse.Namespace) -> int:
    """`say test`: 0 all passed, 3 test failures, 2 compile errors (spec 13 section 5)."""
    from .evaluator import run_checks
    from .explain import Explainer
    from .parser import parse

    passed, failed, rows = 0, 0, []
    for path in test_files(ns.paths):
        text = Path(path).read_text(encoding="utf-8")
        try:
            mod = parse(text + note_examples(text), path, name=Path(path).stem.removesuffix(".test"))
            results = big_stack(lambda m=mod: run_checks(m, allow=tuple(ns.allow or ()), shuffle=ns.shuffle_tasks))
        except SayError as e:
            e.diag.file = e.diag.file or path
            return report(e, path, ns.json)
        checks = {n.line: n for n in C.walk(mod) if isinstance(n, C.Check)}
        for r in results:
            passed, failed = passed + r.ok, failed + (not r.ok)
            rows.append({"file": path, "line": r.line, "label": r.label, "ok": r.ok, "expected": r.expected,
                         "actual": r.actual})  # fmt: skip
            if r.ok or ns.json:
                continue
            if r.error is not None:
                print(r.error.diag.render(text), file=sys.stderr)
                continue
            ex = Explainer(mod)
            if r.line in checks:
                ex.check(checks[r.line], 0)
            why = ex.lines[0].split(": ", 1)[1] if ex.lines else "This check failed."
            print(f"fail[check]: {r.label or 'check'} failed\n  --> {path}:{r.line}:1\n what: expected "
                  f"{r.expected}, actual {r.actual}.\n  why: {why}\n  try: Fix the code or the expected value.\n",
                  file=sys.stderr)  # fmt: skip
    if ns.json:
        print(json.dumps({"version": "say-json/1", "tests": rows, "passed": passed, "failed": failed}))
    else:
        print(f"{passed} passed, {failed} failed")
    return 3 if failed else 0


def cmd_check(ns: argparse.Namespace) -> int:
    """`say check`: parse, resolve and static checks; 0 clean, 2 errors (warnings too with --strict)."""
    from .checker import check_module

    status, diags = 0, []
    for path in ns.paths:
        sink = Sink()
        try:
            _, mod, _ = load(path, sink)
            check_module(mod, sink)
        except SayError as e:
            e.diag.file = e.diag.file or path
            sink.items.append(e.diag)
            status = 2
        text = Path(path).read_text(encoding="utf-8")
        for d in sink.items:
            d.file = d.file or path
            status = 2 if ns.strict or d.severity != "warning" else status
            diags.append(d.to_json()) if ns.json else print(d.render(text), file=sys.stderr)
    if ns.json:
        print(json.dumps({"version": "say-json/1", "diagnostics": diags}))
    return status


def repl(read: Any = input, write: Any = print) -> int:
    """The REPL (spec 13 section 4): echoes canonical input, starts with `console` only."""
    from .evaluator import program
    from .explain import Explainer
    from .parser import parse
    from .printer import print_module
    from .scs import hash_module, show_hash

    surface, caps = "words", ["console"]
    defs: list[str] = []
    lets: list[str] = []

    def source(body: list[str]) -> str:
        need = " and ".join(caps)
        main = "".join("    " + x + "\n" for b in body for x in b.splitlines()) or "    give back nothing\n"
        return f"edition 0\nneeds {need}\n\n" + "\n\n".join(defs) + f"\n\nto main, needs {need}:\n{main}"

    while True:
        try:
            line = read("say> ")
        except EOFError:
            return 0
        while line.rstrip().endswith(":") and not line.startswith(":"):
            more = read("...  ")
            if not more.strip():
                break
            line += "\n" + more
        cmd, _, arg = line.strip().partition(" ")
        try:
            if cmd == ":quit":
                return 0
            elif cmd in (":words", ":symbols"):
                surface = cmd[1:]
            elif cmd == ":caps":
                write(", ".join(caps))
            elif cmd == ":grant":
                if read(f"Grant {arg} to the REPL? (yes/no) ").strip() == "yes":
                    caps.append(arg.split()[0])
            elif cmd == ":load":
                defs.append(Path(arg).read_text(encoding="utf-8").split("\n", 1)[1])
            elif cmd in (":core", ":explain", ":type"):
                mod = parse(source([*lets, f"show ({arg})"]))
                stmt = mod.body[-1].body.stmts[-1].expr.args[0]
                if cmd == ":core":
                    write(repr(stmt))
                elif cmd == ":explain":
                    write(Explainer(mod).np(stmt))
                else:
                    from .values import kind

                    write(kind(program(parse(source([*lets, f"give back ({arg})"])), write)[1]))
            elif cmd == ":hash":
                defs_h, _ = hash_module(parse(source([])))
                write(show_hash(defs_h[arg]) if arg in defs_h else f"no definition named {arg}")
            elif not line.strip():
                continue
            else:
                is_def = line.startswith(("to ", "def ", "ruleset ")) or " has " in line.split("\n")[0]
                body = [] if is_def else [*lets, line]
                trial = source(body) if not is_def else source([]).replace("\n\nto main", "\n\n" + line + "\n\nto main")
                mod = parse(trial)
                printed = print_module(mod, surface)
                chunk = printed.split("\n\n\n")[-2 if is_def else -1].strip()
                write(chunk if is_def else chunk.splitlines()[-1].strip())
                if is_def:
                    defs.append(line)
                elif line.startswith(("let ", "var ")):
                    lets.append(line)
                else:
                    program(mod, write)
        except SayError as e:
            write(e.diag.render())
        except (KeyError, OSError, IndexError) as e:
            write(f"error: {e}")


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
    p = sub.add_parser("explain", help="explain a program in English")
    p.add_argument("file", help="FILE or FILE:LINE")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("check", help="parse and run static checks")
    p.add_argument("paths", nargs="+")
    p.add_argument("--strict", action="store_true")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("test", help="run checks and note examples")
    p.add_argument("paths", nargs="+")
    p.add_argument("--allow", action="append", help="grant a real effect to tests")
    p.add_argument("--shuffle-tasks", type=int, metavar="SEED")
    p.add_argument("--json", action="store_true")
    sub.add_parser("repl", help="interactive session")
    ns = ap.parse_args(argv)
    if ns.version:
        print(version_text())
        return 0
    handler = {
        "fmt": cmd_fmt,
        "hash": cmd_hash,
        "core": cmd_core,
        "run": cmd_run,
        "explain": cmd_explain,
        "check": cmd_check,
        "test": cmd_test,
    }.get(ns.command or "")
    if handler is not None:
        return handler(ns)
    return repl()


if __name__ == "__main__":
    sys.exit(main())
