"""Symbolic core (spec/08-symbolic.md): structural matching, rule application, the pure
`simplify` fallback with cost = node count and SCS-1 tie-break, equivalence, head/arguments."""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from typing import Any

from . import core as C
from .scs import Encoder


@dataclass(frozen=True)
class RulesetV:
    name: str
    rules: tuple[C.Rule, ...]


def is_var(n: Any) -> bool:
    return isinstance(n, C.Name) and n.ref.kind == "patvar"


def match_expr(p: Any, e: Any, binds: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Match expression pattern `p` against core tree `e`; pattern variables bind sub-trees and a
    repeated variable needs structurally equal sub-trees (spec 08 section 5.4)."""
    binds = {} if binds is None else binds
    if is_var(p):
        if p.name in binds:
            return binds if binds[p.name] == e else None
        binds[p.name] = e
        return binds
    if isinstance(p, tuple):
        if not isinstance(e, tuple) or len(p) != len(e):
            return None
        for x, y in zip(p, e, strict=True):
            if match_expr(x, y, binds) is None:
                return None
        return binds
    if isinstance(p, (C.Node, *C.STRUCTS)):
        if type(p) is not type(e):
            return None
        if isinstance(p, C.Name):
            return binds if p.name == getattr(e, "name", None) else None
        if isinstance(p, C.Lit):
            return binds if p == e else None
        for f in fields(p):
            if f.compare and match_expr(getattr(p, f.name), getattr(e, f.name), binds) is None:
                return None
        return binds
    return binds if p == e else None


def substitute(t: Any, binds: dict[str, Any]) -> Any:
    if is_var(t):
        return binds[t.name]
    if isinstance(t, tuple):
        return tuple(substitute(x, binds) for x in t)
    if isinstance(t, (C.Node, *C.STRUCTS)) and not isinstance(t, (C.Lit, C.Ref)):
        return replace(t, **{f.name: substitute(getattr(t, f.name), binds) for f in fields(t) if f.compare})
    return t


def cost(t: Any) -> tuple[int, bytes]:
    """Edition 0 cost: number of core nodes; ties broken by the smallest SCS-1 bytes."""
    return sum(1 for x in C.walk(t) if isinstance(x, C.Node)), Encoder().node(t)


def children(t: Any) -> list[tuple[str, Any]]:
    return [(f.name, getattr(t, f.name)) for f in fields(t) if f.compare]


def rewrite_pass(t: Any, rules: tuple[C.Rule, ...], guard: Any) -> Any:
    """One bottom-up pass applying every rule at every node."""
    if isinstance(t, tuple):
        return tuple(rewrite_pass(x, rules, guard) for x in t)
    if not isinstance(t, C.Node) or isinstance(t, (C.Lit, C.Name, C.SymLit, C.Quote)):
        out = t
    else:
        out = replace(t, **{k: rewrite_pass(v, rules, guard) for k, v in children(t)})
    for r in rules:
        b = match_expr(r.lhs.expr if isinstance(r.lhs, C.PQuote) else r.lhs, out)
        if b is not None and (r.guard is None or guard(r.guard, b)):
            out = substitute(r.rhs, b)
    return out


def simplify(e: Any, rs: RulesetV, guard: Any, nodes: int = 10000, steps: int = 30) -> tuple[Any, bool]:
    """Pure fallback (spec 08 section 6.4): rewrite to a fixpoint keeping the cheapest term.
    Returns (best term, reached a fixpoint within budget)."""
    best, cur = e, e
    for _ in range(steps):
        nxt = rewrite_pass(cur, rs.rules, guard)
        if cost(nxt)[0] > nodes:
            return best, False
        if cost(nxt) < cost(best):
            best = nxt
        if nxt == cur:
            return best, True
        cur = nxt
    return best, False


def head(t: Any) -> str:
    if isinstance(t, C.Call):
        return t.fn.name if isinstance(t.fn, C.Name) else "call"
    return type(t).__name__.lower()


def arguments(t: Any) -> list[Any]:
    if isinstance(t, C.Call):
        return [*t.args, *(v for _, v in t.slots)]
    if isinstance(t, C.Lit):
        return [t.value]
    if isinstance(t, (C.Name, C.SymLit)):
        return [t.name]
    out: list[Any] = []
    for _, v in children(t):
        out.extend(v if isinstance(v, tuple) else [v])
    return out
