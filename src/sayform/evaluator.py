"""Tree-walking evaluator over the core (spec/07-semantics.md).

Every `e_*` method is a generator so concurrency checkpoints can `yield` to the scheduler
(spec 07 section 1.4, spec 11 section 8). Locals are cells keyed by the binding index the
parser assigned; closures share their defining cells (capture by reference).
"""

from __future__ import annotations

import os
import random
from collections.abc import Generator
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from . import core as C
from .diagnostics import SayError, panic
from .values import (
    UNIT_MS,
    ExprV,
    MapV,
    Problem,
    Quantity,
    Record,
    SetV,
    Sym,
    TypeV,
    display,
    equal,
    kind,
    less,
    mismatch,
    specificity,
    type_test,
)

Gen = Generator[Any, Any, Any]
DEPTH_LIMIT = 1500
SAFE = {"from": "from_", "for": "for_"}


class Cell:
    __slots__ = ("v", "mut")

    def __init__(self, v: Any, mut: bool = False) -> None:
        self.v, self.mut = v, mut


@dataclass(slots=True)
class Env:
    cells: dict[int, Cell] = field(default_factory=dict)
    caps: dict[str, Any] = field(default_factory=dict)
    func: Any = None


class Capability:
    """An unforgeable, immutable capability value (spec 09 section 2). `limit` is a resolved
    directory (files) or an integer (tasks); `backing` is an optional CapabilityBacking."""

    NARROWABLE = {"files", "tasks", "network", "environment", "processes"}

    def __init__(self, effect: str, limit: Any = None, read_only: bool = False, backing: Any = None) -> None:
        self.effect, self.limit, self.read_only, self.backing = effect, limit, read_only, backing
        self.revoked = False

    def narrowed(self, narrowing: tuple[Any, ...], line: int = 0) -> Capability:
        limit, ro = self.limit, self.read_only
        for nw in narrowing:
            if nw.kind == "read-only":
                if self.effect != "files":
                    raise SayError("E0504", line, effect=self.effect, x="read only", current="it")
                ro = True
                continue
            arg = nw.arg.value if isinstance(nw.arg, C.Lit) else nw.arg
            if self.effect not in self.NARROWABLE:
                raise SayError("E0504", line, effect=self.effect, x=display(arg, True), current="it")
            if self.effect == "files":
                arg = os.path.realpath(str(arg))
                inside = limit is None or os.path.commonpath([limit, arg]) == limit
            elif self.effect == "tasks":
                inside = limit is None or arg <= limit
            else:
                inside = limit is None or limit == arg
            if not inside:
                raise SayError("E0504", line, effect=self.effect, x=display(arg, True), current=display(limit, True))
            limit = arg
        cap = Capability(self.effect, limit, ro, self.backing)
        cap.parent = self  # type: ignore[attr-defined]
        return cap

    def check(self, use: Any = None) -> Problem | None:
        """Panic if revoked; ask the backing (if any). A non-ok answer is a problem value."""
        cap: Any = self
        while cap is not None:
            if cap.revoked:
                raise panic("E0502", effect=self.effect, reason="it was revoked at the end of a `with` block")
            cap = getattr(cap, "parent", None)
        if self.backing is not None:
            status = self.backing.check(self.effect, (self.limit, self.read_only), use or {})
            if status != "ok":
                return Problem(Sym("capability-revoked"), f"`{self.effect}` is {status}", MapV(reason=status))
        return None

    def path(self, path: Any, write: bool) -> str:
        real = os.path.realpath(str(path))
        if self.limit is not None and os.path.commonpath([self.limit, real]) != self.limit:
            raise panic("E0502", effect="files", reason=f"`{path}` is outside the `files` capability")
        if write and self.read_only:
            raise panic("E0502", effect="files", reason="the `files` capability is read only")
        return real


class ReturnSig(Exception):
    def __init__(self, value: Any) -> None:
        self.value = value


class StopSig(Exception):
    pass


class SkipSig(Exception):
    pass


@dataclass(eq=False)
class Closure:
    name: str
    params: tuple[C.Param, ...]
    body: Any
    env: Env | None
    node: Any = None
    idx: tuple[int, ...] = ()

    @property
    def positional(self) -> list[C.Param]:
        return [p for p in self.params if p.slot in (None, "of")]


@dataclass(eq=False)
class Builtin:
    name: str
    fn: Any
    gen: bool = False
    needs: str = ""


@dataclass(eq=False)
class Generic:
    name: str
    methods: list[Closure]
    fallback: Any = None


@dataclass(eq=False)
class RecordType:
    node: Any  # RecordDef, or a CaseDef with `variant` set
    variant: str = ""

    @property
    def name(self) -> str:
        return str(self.node.name)


def lit_value(n: C.Lit) -> Any:
    if n.kind == "quantity":
        num, unit = n.value
        return Quantity(num * UNIT_MS[unit], unit)
    return n.value


def value_node(v: Any) -> Any:
    """The core node an unquoted value splices as (spec 08 section 2)."""
    if isinstance(v, ExprV):
        return v.node
    if v is None:
        return C.Lit("nothing", None)
    if isinstance(v, bool):
        return C.Lit("truth", v)
    if isinstance(v, int):
        return (
            C.Lit("integer", v) if v >= 0 else C.Call(C.Name("negate", C.Ref("builtin", "negate")), (value_node(-v),))
        )
    if isinstance(v, Decimal):
        return (
            C.Lit("decimal", v) if v >= 0 else C.Call(C.Name("negate", C.Ref("builtin", "negate")), (value_node(-v),))
        )
    if isinstance(v, float):
        return C.Lit("approx", v)
    if isinstance(v, str):
        return C.Lit("text", v)
    if isinstance(v, Sym):
        return C.SymLit(v.name)
    if isinstance(v, tuple) and not isinstance(v, SetV):
        return C.ListLit(tuple(value_node(x) for x in v))
    raise mismatch("unquote", v, expected="an expression or a literal value")


def truth(v: Any, what: str) -> bool:
    if not isinstance(v, bool):
        raise mismatch(what, v, expected="yes or no", reason="condition not yes or no", fix="Compare explicitly")
    return v


class Evaluator:
    """Evaluates one program: the prelude plus the user's module."""

    def __init__(self, write: Any = print) -> None:
        from .builtins import HOST

        self.write = write
        self.host: dict[str, Builtin] = HOST
        self.globals: dict[str, Any] = {}
        self.types: dict[str, RecordType] = {}
        self.variants: dict[str, set[str]] = {}
        self.depth = 0
        self.table = {
            cls: getattr(self, "e_" + cls.__name__) for cls in C.CORE_NODES if hasattr(self, "e_" + cls.__name__)
        }
        self.lam_idx: dict[int, tuple[int, ...]] = {}
        self.read: Any = lambda: None
        self.rng = random.Random()
        self.clock: Decimal | None = None

    # ---- loading -------------------------------------------------------------------------
    def load(self, mod: C.Module) -> Gen:
        for d in mod.body:
            if isinstance(d, C.Func):
                self.define(d)
            elif isinstance(d, C.RecordDef):
                self.types[d.name] = RecordType(d)
            elif isinstance(d, C.VariantDef):
                self.variants[d.name] = {c.name for c in d.cases}
                for c in d.cases:
                    self.types[c.name] = RecordType(c, d.name)
        env = Env()
        for d in mod.body:
            if isinstance(d, C.Bind):
                v = yield from self.ev(d.value, env)
                self.bind(d.target, v, env, top=True)

    def define(self, d: C.Func) -> None:
        clo = Closure(d.name, d.params, d.body, None, d, tuple(range(len(d.params))))
        old = self.globals.get(d.name)
        if isinstance(old, Generic):
            sig = [p.type for p in clo.positional]
            for m in old.methods:
                if [p.type for p in m.positional] == sig:
                    raise SayError("E0402", d.line, fn=d.name, sig1=d.name, sig2=d.name)
            old.methods.append(clo)
        else:
            self.globals[d.name] = Generic(d.name, [clo], self.host.get(d.name))

    # ---- evaluation core -------------------------------------------------------------------
    def ev(self, n: Any, env: Env) -> Gen:
        try:
            return (yield from self.table[type(n)](n, env))
        except SayError as e:
            if not e.diag.line:
                e.diag.line = getattr(n, "line", 0)
            raise

    def block(self, b: Any, env: Env) -> Gen:
        if isinstance(b, C.Block):
            for st in b.stmts:
                yield from self.ev(st, env)
            return None
        return (yield from self.ev(b, env))

    def run(self, gen: Gen) -> Any:
        """Drive a generator to completion (the single-task scheduler)."""
        try:
            while True:
                next(gen)
        except StopIteration as stop:
            return stop.value

    # ---- statements -----------------------------------------------------------------------
    def e_Bind(self, n: C.Bind, env: Env) -> Gen:
        v = yield from self.ev(n.value, env)
        if n.type is not None and not type_test(v, n.type):
            raise mismatch("let", v, expected=display(TypeV(n.type)))
        self.bind(n.target, v, env, mut=n.mutable)

    def bind(self, p: Any, v: Any, env: Env, mut: bool = False, top: bool = False) -> None:
        if top and isinstance(p, C.PBind):
            self.globals[p.name] = v
        elif not self.match(p, v, env, mut):
            raise mismatch("let", v, reason="no case matched", fix="Use `match` for refutable shapes")

    def e_Rebind(self, n: C.Rebind, env: Env) -> Gen:
        v = yield from self.ev(n.value, env)
        cell = env.cells.get(n.name.ref.value)
        if cell is None or not cell.mut:
            raise SayError("E0302", n.line, name=n.name.name)
        cell.v = v

    def e_SetField(self, n: C.SetField, env: Env) -> Gen:
        target = yield from self.ev(n.target, env)
        v = yield from self.ev(n.value, env)
        if not isinstance(target, Record) or not target.changeable:
            raise SayError("E0303", n.line, type=kind(target), value="it", field=n.field)
        if n.field not in target.fields:
            raise SayError("E0206", n.line, type=target.tname, field=n.field, suggestion=n.field)
        target.fields[n.field] = v

    def e_If(self, n: C.If, env: Env) -> Gen:
        for br in n.branches:
            c = yield from self.ev(br.cond, env)
            if truth(c, "if"):
                return (yield from self.block(br.body, env))
        if n.else_ is not None:
            yield from self.block(n.else_, env)
        return None

    def e_Match(self, n: C.Match, env: Env) -> Gen:
        v = yield from self.ev(n.subject, env)
        for case in n.cases:
            if self.match(case.pattern, v, env):
                if case.guard is not None and not truth((yield from self.ev(case.guard, env)), "guard"):
                    continue
                return (yield from self.block(case.body, env))
        if n.else_ is not None:
            return (yield from self.block(n.else_, env))
        raise mismatch("match", v, expected="a value one case accepts", reason="no case matched", fix="Add a case")

    def e_For(self, n: C.For, env: Env) -> Gen:
        src = yield from self.ev(n.source, env)
        if hasattr(src, "drain"):
            src = yield from src.drain(self)
        if not isinstance(src, (tuple, MapV)):
            raise mismatch("for each", src, expected="a list, set or map")
        for x in src:
            self.bind(n.binder, x, env)
            try:
                yield from self.block(n.body, env)
            except StopSig:
                break
            except SkipSig:
                continue
            yield  # loop checkpoint (spec 11 section 8)

    def e_While(self, n: C.While, env: Env) -> Gen:
        while truth((yield from self.ev(n.cond, env)), "while"):
            try:
                yield from self.block(n.body, env)
            except StopSig:
                break
            except SkipSig:
                continue
            yield

    def e_Stop(self, n: C.Stop, env: Env) -> Gen:
        raise StopSig
        yield

    def e_Skip(self, n: C.Skip, env: Env) -> Gen:
        raise SkipSig
        yield

    def e_Return(self, n: C.Return, env: Env) -> Gen:
        v = None if n.value is None else (yield from self.ev(n.value, env))
        raise ReturnSig(v)

    def e_ExprStmt(self, n: C.ExprStmt, env: Env) -> Gen:
        yield from self.ev(n.expr, env)

    def e_WithCap(self, n: C.WithCap, env: Env) -> Gen:
        effect = n.cap.name
        parent = env.caps.get(effect)
        if parent is None:
            raise panic("E0502", effect=effect, reason="the enclosing function does not hold it")
        args = []
        for nw in n.narrowing:
            args.append(C.Narrow(nw.kind, None if nw.arg is None else (yield from self.ev(nw.arg, env))))
        cap = parent.narrowed(tuple(args), n.line)
        try:
            yield from self.block(n.body, Env(env.cells, {**env.caps, effect: cap}, env.func))
        finally:
            cap.revoked = True

    def e_Check(self, n: C.Check, env: Env) -> Gen:
        return None
        yield

    # ---- expressions ------------------------------------------------------------------------
    def e_Lit(self, n: C.Lit, env: Env) -> Gen:
        return lit_value(n)
        yield

    def e_SymLit(self, n: C.SymLit, env: Env) -> Gen:
        return Sym(n.name)
        yield

    def e_Interp(self, n: C.Interp, env: Env) -> Gen:
        out = []
        for p in n.parts:
            out.append(p if isinstance(p, str) else display((yield from self.ev(p, env))))
        return "".join(out)

    def e_Name(self, n: C.Name, env: Env) -> Gen:
        return self.lookup(n, env)
        yield

    def lookup(self, n: C.Name, env: Env) -> Any:
        r = n.ref
        if r.kind == "local":
            cell = env.cells.get(r.value)
            if cell is None:
                raise mismatch(n.name, None, reason="name used before it was bound")
            return cell.v
        if r.kind == "def":
            if r.value in self.globals:
                return self.globals[r.value]
            if r.value in self.types:
                return self.types[r.value]
        if r.kind in ("builtin", "def"):
            if r.value in self.globals:
                return self.globals[r.value]
            if r.value in self.host:
                return self.host[r.value]
        raise SayError("E0304", n.line, name=n.name, suggestion=n.name)

    def e_Get(self, n: C.Get, env: Env) -> Gen:
        t = yield from self.ev(n.target, env)
        if t is None and n.optional:
            return None
        if isinstance(t, Record):
            if n.field in t.fields:
                return t.fields[n.field]
        elif isinstance(t, Problem) and n.field in ("kind", "message", "data"):
            return getattr(t, n.field)
        elif hasattr(t, "get_field"):
            return t.get_field(n.field)
        return Problem(Sym("no-such-field"), f"{kind(t)} has no field `{n.field}`")

    def e_Index(self, n: C.Index, env: Env) -> Gen:
        t = yield from self.ev(n.target, env)
        i = yield from self.ev(n.index, env)
        if t is None and n.optional:
            return None
        return index(t, i, n.optional, n)

    def e_Call(self, n: C.Call, env: Env) -> Gen:
        f = yield from self.ev(n.fn, env)
        args = []
        for a in n.args:
            args.append((yield from self.ev(a, env)))
        kw = {}
        for k, a in n.slots:
            kw[k] = yield from self.ev(a, env)
        return (yield from self.apply(f, args, kw, env, n))

    def apply(self, f: Any, args: list[Any], kw: dict[str, Any], env: Env, node: Any = None) -> Gen:
        if isinstance(f, Builtin):
            if f.needs and f.needs not in env.caps:
                raise panic("E0502", effect=f.needs, reason="the host did not grant it")
            kw = {SAFE.get(k, k).replace("-", "_"): v for k, v in kw.items()}
            if f.gen:
                return (yield from f.fn(self, env, *args, **kw))
            try:
                return f.fn(*args, **kw)
            except TypeError as e:
                if "argument" not in str(e):
                    raise
                raise mismatch(f.name, *args, reason=f"wrong arguments for `{f.name}`") from None
        if isinstance(f, Generic):
            m = self.dispatch(f, args)
            if m is None:
                return (yield from self.apply(f.fallback, args, kw, env, node))
            f = m
        if isinstance(f, Closure):
            return (yield from self.call_closure(f, args, kw, env))
        if isinstance(f, RecordType):
            return (yield from self.construct(f, dict(kw), None, env))
        raise mismatch(
            "call", f, expected="a function", reason="not a function", fix="Two names next to each other mean a call"
        )

    def dispatch(self, g: Generic, args: list[Any]) -> Closure | None:
        ok = [m for m in g.methods if len(m.positional) == len(args)
              and all(type_test(a, p.type) for a, p in zip(args, m.positional, strict=True))]  # fmt: skip
        if not ok:
            if g.fallback is not None:
                return None
            if len(g.methods) == 1:
                return g.methods[0] if len(g.methods[0].positional) != len(args) else self.arg_panic(g, args)
            raise mismatch(g.name, *args, reason=f"no method of `{g.name}` matches (SAY-E0401)", fix="Add a method")

        def rank(m: Closure) -> list[int]:
            return [specificity(p.type) for p in m.positional]

        best = [m for m in ok if all(all(x >= y for x, y in zip(rank(m), rank(o), strict=True)) for o in ok)]
        return best[0] if best else ok[0]

    def arg_panic(self, g: Generic, args: list[Any]) -> Closure:
        p = next(p for a, p in zip(args, g.methods[0].positional, strict=True) if not type_test(a, p.type))
        a = args[g.methods[0].positional.index(p)]
        raise mismatch(g.name, a, expected=display(TypeV(p.type)), reason=f"`{p.name}` has a declared type")

    def call_closure(self, f: Closure, args: list[Any], kw: dict[str, Any], env: Env) -> Gen:
        if self.depth >= DEPTH_LIMIT:
            raise mismatch(f.name, reason="call depth limit reached", fix="Use a loop or a smaller input")
        node = f.node
        caps = env.caps if f.env is None else f.env.caps
        if isinstance(node, C.Func):
            caps = {}
            for e in node.effects:
                if e.effect in env.caps:
                    c = env.caps[e.effect]
                    caps[e.effect] = c.narrowed(e.narrowing, node.line) if e.narrowing else c
        new = Env(dict(f.env.cells) if f.env else {}, caps, f if isinstance(node, C.Func) else env.func)
        pos = iter(args)
        idx = f.idx or self.lambda_indices(f)
        for p, i in zip(f.params, idx, strict=True):
            key = p.name if p.slot == "with" else p.slot
            if p.slot in (None, "of"):
                v = next(pos, StopIteration)
            else:
                v = kw.pop(key, StopIteration) if key else StopIteration
            if v is StopIteration:
                if p.default is None:
                    raise mismatch(f.name, reason=f"`{f.name}` needs `{p.name}`", fix=f"Pass `{p.name}`")
                v = yield from self.ev(p.default, new)
            new.cells[i] = Cell(v)
        if next(pos, StopIteration) is not StopIteration or kw:
            raise mismatch(f.name, *args, reason=f"too many arguments for `{f.name}`")
        self.depth += 1
        try:
            if isinstance(node, C.Lambda):
                return (yield from self.ev(f.body, new))
            yield from self.block(f.body, new)
            result = None
        except ReturnSig as r:
            result = r.value
        finally:
            self.depth -= 1
        if isinstance(node, C.Func) and isinstance(result, Problem) and result.kind.name not in node.fails:
            raise panic("E0207", kind=result.kind.name, fn=f.name)
        return result

    def lambda_indices(self, f: Closure) -> tuple[int, ...]:
        key = id(f.node)
        if key not in self.lam_idx:
            refs: dict[str, int] = {}
            for x in C.walk(f.body):
                if isinstance(x, C.Name) and x.ref.kind == "local":
                    refs[x.name] = min(refs.get(x.name, x.ref.value), x.ref.value)
            fresh = -1 - len(self.lam_idx) * 16
            self.lam_idx[key] = tuple(refs.get(p.name, fresh - i) for i, p in enumerate(f.params))
        return self.lam_idx[key]

    def e_Lambda(self, n: C.Lambda, env: Env) -> Gen:
        return Closure("function", n.params, n.body, env, n)
        yield

    def e_ListLit(self, n: C.ListLit, env: Env) -> Gen:
        out = []
        for x in n.items:
            out.append((yield from self.ev(x, env)))
        return tuple(out)

    def e_SetLit(self, n: C.SetLit, env: Env) -> Gen:
        out: list[Any] = []
        for x in n.items:
            v = yield from self.ev(x, env)
            if not any(equal(v, y) for y in out):
                out.append(v)
        return SetV(out)

    def e_MapLit(self, n: C.MapLit, env: Env) -> Gen:
        out = MapV()
        for k, x in n.pairs:
            key = yield from self.ev(k, env)
            out[key] = yield from self.ev(x, env)
        return out

    def e_RecordLit(self, n: C.RecordLit, env: Env) -> Gen:
        kw = {}
        for k, x in n.fields:
            kw[k] = yield from self.ev(x, env)
        if n.base is not None:
            base = yield from self.ev(n.base, env)
            if not isinstance(base, Record):
                raise mismatch("with", base, expected="a record")
            rt: RecordType | None = self.types[base.case or base.tname]
            assert rt is not None
            for k in kw:
                if k not in base.fields:
                    raise SayError("E0206", n.line, type=rt.name, field=k, suggestion=next(iter(base.fields), k))
            return (yield from self.construct(rt, {**base.fields, **kw}, base, env))
        rt = self.types.get(n.type.ref) if isinstance(n.type, C.TName) else None
        if rt is None:
            raise SayError("E0304", n.line, name=display(TypeV(n.type)), suggestion="")
        return (yield from self.construct(rt, kw, None, env))

    def construct(self, rt: RecordType, kw: dict[str, Any], base: Any, env: Env) -> Gen:
        d = rt.node
        cells, vals = Env(), {}
        for i, fd in enumerate(d.fields):
            if fd.name in kw:
                v = kw.pop(fd.name)
            elif fd.default is not None:
                v = yield from self.ev(fd.default, cells)
            else:
                raise SayError("E0211", type=rt.name, field=fd.name)
            if not type_test(v, fd.type):
                raise mismatch(f"{rt.name} with {fd.name}", v, expected=display(TypeV(fd.type)))
            vals[fd.name] = v
            cells.cells[i] = Cell(v)
        if kw:
            k = next(iter(kw))
            raise SayError("E0206", type=rt.name, field=k, suggestion=d.fields[0].name if d.fields else k)
        for inv in getattr(d, "invariants", ()):
            if not truth((yield from self.ev(inv, cells)), "where"):
                from .printer import print_expr

                rule = print_expr(inv, "words")
                return Problem(Sym("invalid"), f"{rt.name} must satisfy: {rule}", MapV(rule=rule))
        if rt.variant:
            return Record(rt.variant, vals, d.name)
        return Record(d.name, vals, None, bool(d.changeable))

    def e_TypeTest(self, n: C.TypeTest, env: Env) -> Gen:
        v = yield from self.ev(n.value, env)
        return type_test(v, n.type)

    def e_TypeExpr(self, n: C.TypeExpr, env: Env) -> Gen:
        return TypeV(n.type)
        yield

    def e_Try(self, n: C.Try, env: Env) -> Gen:
        v = yield from self.ev(n.expr, env)
        if isinstance(v, Problem):
            raise ReturnSig(v)
        return v

    def e_Quote(self, n: C.Quote, env: Env) -> Gen:
        return ExprV((yield from self.splice(n.expr, env)))

    def splice(self, n: Any, env: Env) -> Gen:
        if isinstance(n, C.Unquote):
            return value_node((yield from self.ev(n.expr, env)))
        if (
            isinstance(n, C.Quote)
            or not isinstance(n, (C.Node, tuple))
            or not any(isinstance(x, C.Unquote) for x in C.walk(n))
        ):
            return n
        if isinstance(n, tuple):
            out = []
            for x in n:
                out.append((yield from self.splice(x, env)))
            return tuple(out)
        from dataclasses import fields, replace

        changes = {}
        for f in fields(n):
            if f.compare:
                changes[f.name] = yield from self.splice(getattr(n, f.name), env)
        return replace(n, **changes)

    # ---- patterns (spec 07 section 5) ---------------------------------------------------------
    def match(self, p: Any, v: Any, env: Env, mut: bool = False) -> bool:
        if isinstance(p, C.PBind):
            if p.type is not None and not type_test(v, p.type):
                return False
            if p.ref is not None:
                env.cells[p.ref.value] = Cell(v, mut)
            return True
        if isinstance(p, C.PWild):
            return True
        if isinstance(p, C.PLit):
            return equal(lit_value(p.lit) if isinstance(p.lit, C.Lit) else p.lit, v)
        if isinstance(p, (C.PRecord, C.PCase)):
            if not isinstance(v, Record):
                return False
            if isinstance(p, C.PCase) and v.case != p.case:
                return False
            if isinstance(p, C.PRecord) and v.tname != getattr(p.type, "ref", p.type):
                return False
            if not p.open and len(p.fields) not in (0, len(v.fields)) and isinstance(p, C.PRecord):
                return False
            return all(k in v.fields and self.match(sub, v.fields[k], env) for k, sub in p.fields)
        if isinstance(p, C.PList):
            if type(v) is not tuple or len(v) < len(p.prefix) or (p.rest is None and len(v) != len(p.prefix)):
                return False
            if not all(self.match(sub, x, env) for sub, x in zip(p.prefix, v, strict=False)):
                return False
            return p.rest is None or self.match(p.rest, v[len(p.prefix) :], env)
        if isinstance(p, C.PRange):
            lo, hi = (lit_value(x.lit) if isinstance(x, C.PLit) else lit_value(x) for x in (p.lo, p.hi))
            try:
                return not less(v, lo) and (less(v, hi) or (p.inclusive and equal(v, hi)))
            except SayError:
                return False
        if isinstance(p, C.PAlt):
            return any(self.match(a, v, env) for a in p.alts)
        if isinstance(p, C.PQuote):
            from .symbolic import match_expr  # type: ignore[import-untyped, unused-ignore]

            got = match_expr(p.expr, v.node if isinstance(v, ExprV) else value_node(v))
            if got is None:
                return False
            for name, sub in got.items():
                for x in C.walk(p.expr):
                    if isinstance(x, C.PBind) and x.name == name and x.ref is not None:
                        env.cells[x.ref.value] = Cell(ExprV(sub))
            return True
        return False


def index(t: Any, i: Any, optional: bool, n: Any = None) -> Any:
    """`item i of c` (spec 05 section 6): 1-based, negative from the end, ranges slice."""
    if isinstance(t, MapV):
        if i in t:
            return t[i]
        if optional:
            return None
        params: dict[str, Any] = {"index/key": "Key " + display(i, True), "expr": src(n), "n": len(t)}
        raise panic("E0832", **params)
    if type(t) is not tuple:
        raise mismatch("item", t, expected="a list or a map")
    if type(i) is tuple:
        return tuple(index(t, j, optional) for j in i)
    if isinstance(i, float):
        raise SayError("E0801", severity="panic", expr=display(i), context="an index")
    if not isinstance(i, int) or isinstance(i, bool):
        raise mismatch("item", i, expected="an integer")
    if i == 0:
        raise panic("E0831")
    j = i - 1 if i > 0 else len(t) + i
    if 0 <= j < len(t):
        return t[j]
    if optional:
        return None
    params = {"index/key": f"Item {i}", "expr": src(n), "n": len(t)}
    raise panic("E0832", **params)


def src(n: Any) -> str:
    from .printer import print_expr

    return print_expr(n.target) if isinstance(n, C.Index) else "the list"


def prelude_module() -> C.Module:
    from pathlib import Path

    from .parser import parse

    here = Path(__file__).resolve().parent
    for d in (here / "prelude", here.parents[1] / "prelude"):
        f = d / "prelude.say"
        if f.exists():
            return parse(f.read_text(encoding="utf-8"), str(f), name="prelude")
    raise RuntimeError("prelude not found")


_PRELUDE: list[C.Module] = []


HOST_EFFECTS = {"console", "files", "clock", "random", "tasks"}


def program(
    mod: C.Module, write: Any = print, read: Any = None, grant: Any = None, backing: Any = None, seed: Any = None
) -> tuple[Evaluator, Any]:
    """Load prelude and `mod`, then call `main` with the capabilities it declares that the
    host grants (spec 07 section 1.5). Returns the evaluator and main's result."""
    from .checker import check_module

    check_module(mod)
    if not _PRELUDE:
        _PRELUDE.append(prelude_module())
    ev = Evaluator(write)
    ev.read = read or (lambda: None)
    if seed is not None:
        ev.rng.seed(seed)
        ev.clock = Decimal(0)
    ev.globals["empty-set"] = SetV(())
    ev.run(ev.load(_PRELUDE[0]))
    ev.run(ev.load(mod))
    main = ev.globals.get("main")
    if not isinstance(main, Generic):
        return ev, None
    effects = main.methods[0].node.effects
    caps: dict[str, Capability] = {}
    for e in effects:
        if e.effect not in HOST_EFFECTS or (grant is not None and not grant(e.effect)):
            why = "not implemented in this version" if e.effect not in HOST_EFFECTS else "`--deny`"
            params: dict[str, Any] = {"effect": e.effect, "policy source": why}
            raise SayError("E0506", main.methods[0].node.line, **params)
        caps[e.effect] = Capability(e.effect, backing=backing)
    env = Env(caps=caps)
    return ev, ev.run(ev.apply(main, [], {}, env))
