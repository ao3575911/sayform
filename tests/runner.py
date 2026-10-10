"""Shared helper: run a Sayform program in-process and capture output, exit code and diagnostic."""

from __future__ import annotations

from dataclasses import dataclass

from sayform.cli import big_stack
from sayform.diagnostics import EXIT, SayError
from sayform.evaluator import program
from sayform.parser import parse
from sayform.values import Problem


@dataclass
class Result:
    out: list[str]
    exit: int
    code: str = ""
    what: str = ""
    value: object = None
    trace: tuple[str, ...] = ()


def run(body: str, header: str = "", needs: str = "console", stdin: list[str] | None = None) -> Result:
    """Run `body` as the block of `main` (indented automatically), after `header` definitions."""
    main = "".join("    " + ln + "\n" if ln else "\n" for ln in body.splitlines())
    head = f"needs {needs}\n" if needs else ""
    src = f"edition 0\n{head}\n{header}\n\nto main{', needs ' + needs if needs else ''}:\n{main}"
    return run_source(src, stdin)


def run_source(src: str, stdin: list[str] | None = None) -> Result:
    out: list[str] = []
    lines = list(stdin or [])

    def write(text: str, end: str = "\n") -> None:
        out.append(text)

    try:
        _, value = big_stack(lambda: program(parse(src), write, lambda: lines.pop(0) if lines else None))
    except SayError as e:
        return Result(out, EXIT[e.diag.severity], e.code, e.diag.what, trace=tuple(e.diag.trace))
    return Result(out, 1 if isinstance(value, Problem) else 0, value=value)


def shows(body: str, header: str = "") -> list[str]:
    r = run(body, header)
    assert r.exit == 0, f"{r.code}: {r.what}"
    return r.out
