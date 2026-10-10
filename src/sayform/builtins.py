"""Host primitives (spec/12-stdlib.md section 2). Grouped by spec subsection.

Each builtin checks its argument types at run time and panics with SAY-E0212 on a
mismatch (spec 05 section 1.1). Slot keywords arrive as Python-safe names (`from_`).
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from typing import Any, TypeVar

from . import values as V
from .diagnostics import SayError, panic
from .evaluator import Builtin, Env, Evaluator, Gen
from .values import MapV, Problem, SetV, Sym, display, equal, graphemes, mismatch

HOST: dict[str, Builtin] = {}


F = TypeVar("F", bound=Callable[..., Any])


def host(name: str, gen: bool = False, needs: str = "") -> Callable[[F], F]:
    def deco(fn: F) -> F:
        HOST[name] = Builtin(name, fn, gen, needs)
        return fn

    return deco


def text_arg(op: str, *ts: Any) -> None:
    for t in ts:
        if not isinstance(t, str):
            raise mismatch(op, t, expected="text")


# ---- 2.1 core ----------------------------------------------------------------------------
host("equal")(equal)


@host("same")
def same(a: Any, b: Any) -> bool:
    mutable = isinstance(a, V.Record) and a.changeable
    return a is b or (not mutable and not callable(getattr(a, "call", None)) and equal(a, b))


@host("not")
def not_(a: Any) -> bool:
    if not isinstance(a, bool):
        raise mismatch("not", a, expected="yes or no", fix="`not` takes a truth; use `or else` for defaults")
    return not a


def logic(name: str) -> None:
    @host(name, gen=True)
    def fn(ev: Evaluator, env: Env, a: Any, b: Any) -> Gen:
        if not isinstance(a, bool):
            raise mismatch(name, a, expected="yes or no", fix="Use `or else` for a default value")
        if a is (name == "or"):
            return a
        r = yield from ev.apply(b, [], {}, env)
        if not isinstance(r, bool):
            raise mismatch(name, r, expected="yes or no")
        return r


logic("and")
logic("or")


@host("default", gen=True)
def default(ev: Evaluator, env: Env, a: Any, b: Any) -> Gen:
    if a is None or isinstance(a, Problem):
        return (yield from ev.apply(b, [], {}, env))
    return a


@host("problem")
def problem(kind: Any, message: str = "", data: Any = None) -> Problem:
    if not isinstance(kind, Sym):
        raise mismatch("problem", kind, expected="a symbol")
    text_arg("problem", message)
    return Problem(kind, message, data if data is not None else MapV())


host("display")(lambda value: display(value))


# ---- 2.2 console -------------------------------------------------------------------------
@host("show", gen=True, needs="console")
def show(ev: Evaluator, env: Env, value: Any) -> Gen:
    bad = env.caps["console"].check()
    if bad is None:
        ev.write(display(value))
    return bad
    yield


@host("ask", gen=True, needs="console")
def ask(ev: Evaluator, env: Env, prompt: Any) -> Gen:
    text_arg("ask", prompt)
    bad = env.caps["console"].check()
    if bad is not None:
        return bad
    ev.write(prompt, end="")
    line = ev.read()
    return Problem(Sym("not-found"), "end of input") if line is None else line
    yield


# ---- 2.3 numbers -------------------------------------------------------------------------
for _op in ("add", "subtract", "multiply", "divide", "floor-divide", "modulo"):
    host(_op)(lambda a, b, _op=_op: V.arith(_op, a, b))
host("power")(V.power)
host("negate")(V.negate)
host("less")(V.less)


@host("round")
def round_(x: Any, places: Any = 0, mode: Any = None) -> Any:
    if mode is not None and (not isinstance(mode, Sym) or mode.name not in ("half-even", "half-up")):
        raise mismatch("round", mode, expected="'half-even or 'half-up")
    return V.round_num(x, places, mode)


# ---- 2.4 text ----------------------------------------------------------------------------
@host("length")
def length(t: Any) -> int:
    text_arg("length", t)
    return len(graphemes(t))


@host("uppercase")
def uppercase(t: Any) -> str:
    text_arg("uppercase", t)
    return str(t).upper()


@host("lowercase")
def lowercase(t: Any) -> str:
    text_arg("lowercase", t)
    return str(t).lower()


@host("join")
def join(a: Any, b: Any) -> Any:
    if isinstance(a, str) and isinstance(b, str):
        return a + b
    if type(a) is tuple and type(b) is tuple:
        return a + b
    if isinstance(a, str) or isinstance(b, str):
        raise panic("E0202", a=display(a, True), op="++", b=display(b, True))
    raise mismatch("join", a, b, expected="two texts or two lists")


@host("split")
def split(t: Any, by: Any) -> tuple[str, ...]:
    text_arg("split", t, by)
    if by == "":
        raise mismatch("split", by, expected="a non-empty separator")
    return tuple(t.split(by))


@host("trim")
def trim(t: Any) -> str:
    text_arg("trim", t)
    return str(t).strip()


@host("code-points")
def code_points(t: Any) -> tuple[int, ...]:
    text_arg("code-points", t)
    return tuple(ord(c) for c in t)


@host("utf8-bytes")
def utf8_bytes(t: Any) -> tuple[int, ...]:
    text_arg("utf8-bytes", t)
    return tuple(t.encode("utf-8"))


@host("parse-number")
def parse_number(t: Any) -> Any:
    text_arg("parse-number", t)
    s = t[1:] if t.startswith("-") else t
    ok = s.replace("_", "").isdigit() or (s.count(".") == 1 and all(p.isdigit() for p in s.split(".")))
    if not ok or not s or s.startswith("_"):
        return Problem(Sym("parse-error"), f'"{t}" is not a number')
    try:
        v = Decimal(t.replace("_", "")) if "." in t else int(t.replace("_", ""))
    except (InvalidOperation, ValueError):
        return Problem(Sym("parse-error"), f'"{t}" is not a number')
    return v


# ---- 2.5 collections ----------------------------------------------------------------------
@host("range")
def range_(a: Any, b: Any, exclusive: Any = False, step: Any = 1) -> tuple[Any, ...]:
    for x in (a, b, step):
        if isinstance(x, float):
            raise SayError("E0801", severity="panic", expr=display(x), context="a range bound")
        if not V.exact(x):
            raise mismatch("range", x, expected="an exact number")
    if step == 0:
        raise SayError("E0802", severity="panic")
    out, x = [], a
    while (x < b or (not exclusive and x == b)) if step > 0 else (x > b or (not exclusive and x == b)):
        out.append(x)
        x = V.arith("add", x, step)
    return tuple(out)


@host("added")
def added(c: Any, item: Any) -> Any:
    if isinstance(c, SetV):
        return c if V.contains(c, item) else SetV((*c, item))
    if type(c) is tuple:
        return (*c, item)
    if isinstance(c, MapV) and isinstance(item, MapV):
        return MapV({**c, **item})
    if V.is_num(c) or isinstance(c, V.Quantity):
        return V.arith("add", c, item)  # spec gap: `add 1 to n` on a number adds
    raise mismatch("added", c, item, expected="a list, set, or a map and a map")


@host("count")
def count(c: Any) -> int:
    if isinstance(c, str):
        return len(graphemes(c))
    if isinstance(c, (tuple, MapV)):
        return len(c)
    raise mismatch("count", c, expected="a list, set, map or text")


@host("sort-by", gen=True)
def sort_by(ev: Evaluator, env: Env, c: Any, key: Any, descending: Any = False) -> Gen:
    if not isinstance(c, tuple):
        raise mismatch("sort-by", c, expected="a list or set")
    keys = []
    for x in c:
        keys.append((yield from ev.apply(key, [x], {}, env)))
    kinds = {"number" if V.is_num(k) else "text" if isinstance(k, str) else V.kind(k) for k in keys}
    if len(kinds) > 1 or kinds - {"number", "text"}:
        raise SayError("E0803", severity="panic", types=", ".join(sorted(kinds)))
    order = sorted(range(len(c)), key=lambda i: keys[i], reverse=bool(descending))
    return tuple(c[i] for i in order)


host("contains")(V.contains)


@host("keys")
def keys(m: Any) -> tuple[Any, ...]:
    if not isinstance(m, MapV):
        raise mismatch("keys", m, expected="a map")
    return tuple(m)


@host("values")
def values(m: Any) -> tuple[Any, ...]:
    if not isinstance(m, MapV):
        raise mismatch("values", m, expected="a map")
    return tuple(m.values())


# ---- 2.8 host-effect modules -------------------------------------------------------------
@host("files.read-text", gen=True, needs="files")
def read_text(ev: Evaluator, env: Env, path: Any) -> Gen:
    text_arg("files.read-text", path)
    cap = env.caps["files"]
    bad = cap.check({"path": path})
    if bad is not None:
        return bad
    real = cap.path(path, write=False)
    try:
        with open(real, encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        return Problem(Sym("not-found"), f"cannot read `{path}`: {e.strerror}")
    yield


@host("files.write-text", gen=True, needs="files")
def write_text(ev: Evaluator, env: Env, content: Any, to: Any) -> Gen:
    text_arg("files.write-text", content, to)
    cap = env.caps["files"]
    bad = cap.check({"path": to})
    if bad is not None:
        return bad
    with open(cap.path(to, write=True), "w", encoding="utf-8") as f:
        f.write(content)
    return None
    yield


@host("clock.now", gen=True, needs="clock")
def now(ev: Evaluator, env: Env) -> Gen:
    bad = env.caps["clock"].check()
    if bad is not None:
        return bad
    if ev.clock is not None:
        return ev.clock.quantize(Decimal("0.000001"))
    import time

    return Decimal(time.time_ns() // 1000).scaleb(-6)
    yield


@host("random.random-integer", gen=True, needs="random")
def random_integer(ev: Evaluator, env: Env, from_: Any, to: Any) -> Gen:
    for x in (from_, to):
        if not isinstance(x, int) or isinstance(x, bool):
            raise mismatch("random-integer", x, expected="an integer")
    bad = env.caps["random"].check()
    return bad if bad is not None else ev.rng.randint(from_, to)
    yield
