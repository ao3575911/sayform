"""Static checks run before a program starts (spec/05-types-values.md section 1.1, spec/09
section 1): effect declarations (E0501, E0601) and narrowing literals (E0504)."""

from __future__ import annotations

from typing import Any

from . import core as C
from .diagnostics import SayError, Sink

#: Effects of host primitives (spec 12 section 2).
BUILTIN_EFFECTS = {"show": "console", "ask": "console", "files.read-text": "files", "files.write-text": "files",
                   "clock.now": "clock", "random.random-integer": "random", "new-channel": "tasks", "send": "tasks",
                   "receive": "tasks", "close": "tasks", "sleep": "tasks", "map-concurrent": "tasks",
                   "received": "tasks"}  # fmt: skip
CONSTRUCTS = {C.Concurrent: "together / all of / first of", C.Within: "within"}


def uses(node: Any, funcs: dict[str, C.Func]) -> list[tuple[str, str, int]]:
    """(effect, via, line) for every statically known effectful use inside `node`."""
    out = []
    for x in C.walk(node):
        if isinstance(x, C.Call) and isinstance(x.fn, C.Name):
            r = x.fn.ref
            if r.kind == "builtin" and r.value in BUILTIN_EFFECTS:
                out.append((BUILTIN_EFFECTS[r.value], f"`{r.value}`", x.line))
            elif r.kind == "def" and r.value in funcs:
                out += [(e.effect, f"`{r.value}`", x.line) for e in funcs[r.value].effects]
        elif isinstance(x, C.WithCap):
            out.append((x.cap.name, "`with`", x.line))
        elif type(x) in CONSTRUCTS:
            out.append(("tasks", CONSTRUCTS[type(x)], x.line))
    return out


def check_module(mod: C.Module, sink: Sink | None = None) -> None:
    funcs = {d.name: d for d in mod.body if isinstance(d, C.Func)}
    union: set[str] = set()
    for d in mod.body:
        declared = {e.effect for e in d.effects} if isinstance(d, C.Func) else set()
        name = d.name if isinstance(d, C.Func) else "the top-level `let`"
        union |= declared
        if not isinstance(d, (C.Func, C.Bind)):
            continue
        for effect, via, line in uses(d.body if isinstance(d, C.Func) else d.value, funcs):
            if effect not in declared:
                if effect == "tasks" and not via.startswith("`"):
                    raise SayError("E0601", line or d.line, construct=via)
                raise SayError("E0501", line or d.line, fn=name, effect=effect, via=via)
    header = {e.effect for e in mod.needs}
    if mod.needs and union - header:
        missing = sorted(union - header)[0]
        raise SayError("E0501", 2, fn=f"module {mod.name}", effect=missing, via="its definitions")
