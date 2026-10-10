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
    for d in mod.body:
        if isinstance(d, C.Func):
            check_tasks(d, funcs)
    check_dialect(mod, sink)
    check_static(mod, sink)
    header = {e.effect for e in mod.needs}
    if mod.needs and union - header:
        missing = sorted(union - header)[0]
        raise SayError("E0501", 2, fn=f"module {mod.name}", effect=missing, via="its definitions")


def can_fail(node: Any, funcs: dict[str, C.Func]) -> bool:
    for x in C.walk(node):
        if isinstance(x, (C.Try, C.Within)):
            return True
        if isinstance(x, C.Call) and isinstance(x.fn, C.Name) and x.fn.ref.kind == "def":
            f = funcs.get(x.fn.ref.value)
            if f is not None and f.fails:
                return True
    return False


def check_tasks(fn: C.Func, funcs: dict[str, C.Func]) -> None:
    """Spec 11: E0603 (child captures changeable state), E0605 (`within` limit literal is not a
    time), E0606 (`several` not declared), E0207 (`timed-out` not declared)."""
    changeable = {
        x.target.ref.value: x.target.name
        for x in C.walk(fn.body)
        if isinstance(x, C.Bind) and x.mutable and isinstance(x.target, C.PBind) and x.target.ref
    }
    for x in C.walk(fn.body):
        if isinstance(x, C.Within):
            if isinstance(x.limit, C.Lit) and x.limit.kind != "quantity":
                raise SayError("E0605", x.line, expr=str(x.limit.value))
            if "timed-out" not in fn.fails:
                raise SayError("E0207", x.line, kind="timed-out", fn=fn.name)
        if not isinstance(x, C.Concurrent):
            continue
        for ch in x.children:
            for y in C.walk(ch.body):
                if isinstance(y, C.Name) and y.ref.kind == "local" and y.ref.value in changeable:
                    raise SayError("E0603", x.line, name=y.name)
        if sum(can_fail(ch.body, funcs) for ch in x.children) >= 2 and "several" not in fn.fails:
            raise SayError("E0606", x.line)


def check_dialect(mod: C.Module, sink: Sink | None) -> None:
    """Exhaustive variant matches (W0911, an error under `strict`) and the `strict` dialect:
    ASCII names (E0124) and typed exports (E0205) (spec 10 section 2.7)."""
    strict = "strict" in mod.dialects
    cases = {c.name: v for v in mod.body if isinstance(v, C.VariantDef) for c in v.cases}
    for x in C.walk(mod):
        if isinstance(x, C.Match) and x.else_ is None and all(c.guard is None for c in x.cases):
            pats = [p for c in x.cases for p in (c.pattern.alts if isinstance(c.pattern, C.PAlt) else (c.pattern,))]
            if pats and all(isinstance(p, C.PCase) and p.case in cases for p in pats):
                missing = [c.name for c in cases[pats[0].case].cases if c.name not in {p.case for p in pats}]
                if missing and strict:
                    raise SayError("W0911", x.line, severity="error", missing=", ".join(missing))
                if missing and sink is not None:
                    sink.warn("W0911", x.line, missing=", ".join(missing))
        if strict and isinstance(x, (C.Name, C.PBind, C.Func, C.Param)) and not x.name.isascii():
            raise SayError("E0124", getattr(x, "line", 0), word=x.name)
    for d in mod.body:
        if strict and isinstance(d, C.Func) and (d.result is None or any(p.type is None for p in d.params)):
            if d.name != "main" or any(p.type is None for p in d.params):
                raise SayError("E0205", d.line, name=d.name)


NUMS = {"integer", "decimal", "approx"}
ORDER = {"less", "less-eq", "greater", "greater-eq"}
KINDS = {C.ListLit: "a list", C.MapLit: "a map", C.SetLit: "a set", C.Interp: "text", C.RecordLit: "a record"}


def kind_of(n: Any) -> str | None:
    """The static kind of a literal-shaped node, or None when it is not known statically."""
    if isinstance(n, C.Lambda) and not n.params:
        return kind_of(n.body)
    if isinstance(n, C.Lit):
        return {"truth": "truth", "text": "text", "quantity": "time"}.get(n.kind, "number" if n.kind in NUMS else None)
    return KINDS.get(type(n))


def check_static(mod: C.Module, sink: Sink | None) -> None:
    """Static checks of spec 05 section 1.1 and spec 06/07: `=` as a statement (E0111), no
    truthiness (E0112, E0201), dimensions (E0203), call shape (E0408-E0410), orphan methods
    (E0403), duplicate literal keys (E0821) and ignored problems (W0201)."""
    from .lower import HOST_SIGS, PRELUDE_NAMES

    names = [d.name for d in mod.body if isinstance(d, C.Func)]
    funcs = {d.name: d for d in mod.body if isinstance(d, C.Func) and names.count(d.name) == 1}
    owned = {d.name for d in mod.body if isinstance(d, (C.RecordDef, C.VariantDef))}
    for d in mod.body:
        if isinstance(d, C.Func) and (d.name in HOST_SIGS or d.name in PRELUDE_NAMES):
            types = [p.type.ref for p in d.params if isinstance(p.type, C.TName)]
            if not set(types) & owned:
                raise SayError("E0403", d.line, fn=d.name, types=", ".join(types) or "untyped parameters")
    for x in C.walk(mod):
        line = getattr(x, "line", 0)
        if isinstance(x, C.ExprStmt) and isinstance(x.expr, C.Call) and isinstance(x.expr.fn, C.Name):
            fn, args = x.expr.fn, x.expr.args
            if fn.ref.kind == "builtin" and fn.name == "equal" and isinstance(args[0], C.Name):
                raise SayError("E0111", line, name=args[0].name)
            if fn.ref.kind == "def" and fn.name in funcs and funcs[fn.name].fails and sink is not None:
                sink.warn("W0201", line, call=fn.name)
        if isinstance(x, (C.If, C.While)):
            for cond in [b.cond for b in x.branches] if isinstance(x, C.If) else [x.cond]:
                k = kind_of(cond)
                if k not in (None, "truth"):
                    raise SayError("E0201", line, expected="yes or no", actual=k, context="Conditions must be Truth",
                                   fix="Compare explicitly, for example `n is greater than 0`")  # fmt: skip
        if isinstance(x, (C.MapLit, C.SetLit)):
            keys = [k for k, _ in x.pairs] if isinstance(x, C.MapLit) else list(x.items)
            lits = [(k.kind, repr(k.value)) for k in keys if isinstance(k, C.Lit)]
            dup = next((k for k in lits if lits.count(k) > 1), None)
            if dup is not None:
                raise SayError("E0821", line, key=dup[1])
        if not (isinstance(x, C.Call) and isinstance(x.fn, C.Name)):
            continue
        name, kinds = x.fn.name, [kind_of(a) for a in x.args]
        if x.fn.ref.kind == "builtin" and name in ("and", "or", "not"):
            bad = next((k for k in kinds if k not in (None, "truth")), None)
            if bad is not None:
                raise SayError("E0112", line, op=name, type=bad)
        if x.fn.ref.kind == "builtin" and name in {"add", "subtract", *ORDER} and len(kinds) == 2:
            if "time" in kinds and kinds[0] != kinds[1] and None not in kinds:
                raise SayError("E0203", line, a=expr(x.args[0]), b=expr(x.args[1]), dim1=kinds[0], dim2=kinds[1])
            if name in ORDER and {"text", "number"} == set(kinds):
                raise SayError("E0201", line, expected=kinds[0], actual=kinds[1], context=f"`{name}` compares like with like",
                               fix="Convert one side first")  # fmt: skip
        if x.fn.ref.kind == "def" and name in funcs:
            call_shape(funcs[name], x)


def expr(n: Any) -> str:
    from .printer import print_expr

    return print_expr(n)


def call_shape(f: C.Func, call: C.Call) -> None:
    """Spec 03 section 7.1: positional, slot and named arguments against the signature."""
    keys = [k for k, _ in call.slots]
    key = {p.name: p.name if p.slot == "with" else p.slot for p in f.params if p.slot not in (None, "of")}
    for k in keys:
        if k not in key.values():
            raise SayError("E0408", call.line, fn=f.name, name=k, params=", ".join(sorted(key.values())) or "none")
        if keys.count(k) > 1:
            raise SayError("E0410", call.line, fn=f.name, problem=f"`{k}` twice")
    free = [p for p in f.params if key.get(p.name) not in keys]
    if len(call.args) > len(free):
        raise SayError("E0410", call.line, fn=f.name, problem=f"{len(call.args)} positional arguments for {len(free)}")
    for p in free[len(call.args) :]:
        if p.default is None:
            raise SayError("E0409", call.line, fn=f.name, param=p.name, lead=key.get(p.name) or p.name)
