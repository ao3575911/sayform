"""Round-trip laws L1-L5 (spec/04-core-ast.md section 4), RT-L1..RT-L5, RT-MUT, RT-CORPUS.

Expression trees are generated directly as core (Hypothesis, depth <= 6, width <= 5) and
placed in a fixed module; laws are checked by printing in each surface and parsing back.
Set SAYFORM_RT_EXAMPLES=10000 for the nightly run.
"""

from __future__ import annotations

import os
import unicodedata
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from sayform import core as C
from sayform import printer as P
from sayform.keywords import RESERVED_SET
from sayform.lexer import lex
from sayform.parser import make_union, parse, transform
from sayform.printer import print_module
from sayform.scs import hash_module

EXAMPLES = int(os.environ.get("SAYFORM_RT_EXAMPLES", "200"))
ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = "module rt\nedition 0\n\n\na Box has a size (a number)\n\n\nto g of v:\n    give back v\n\n\nto f x y:\n    let result be 0\n    give back result\n"
BASE = parse(TEMPLATE, name="rt")
POOL = [w for w in ("lett", "be-ok", "times-up", "least", "back", "size", "total", "naïve") if w not in RESERVED_SET]


def b(name: str, args: list[Any], slots: tuple[tuple[str, Any], ...] = ()) -> C.Call:
    return C.Call(C.Name(name, C.Ref("builtin", name)), tuple(args), slots)


def thunk(x: Any) -> C.Lambda:
    return C.Lambda((), x)


PIECES = [*'ab {}\\"\n\t', "e\u0301", "\U0001f44d\U0001f3fd", '"""', "\u0007"]
TEXTS = st.lists(st.sampled_from(PIECES), max_size=6).map(lambda xs: unicodedata.normalize("NFC", "".join(xs)))
LEAVES = st.one_of(
    st.integers(0, 10**6).map(lambda n: C.Lit("integer", n)),
    st.just(C.Lit("integer", 10**199 + 7)),
    st.sampled_from(["12.50", "12.5", "0.10", "3.0"]).map(lambda s: C.Lit("decimal", Decimal(s))),
    st.sampled_from([0.0, 0.1, 2.5, 1e20]).map(lambda f: C.Lit("approx", f)),
    TEXTS.map(lambda s: C.Lit("text", s)),
    st.booleans().map(lambda v: C.Lit("truth", v)),
    st.just(C.Lit("nothing", None)),
    st.sampled_from([("x", 0), ("y", 1)]).map(lambda p: C.Name(p[0], C.Ref("local", p[1]))),
    st.sampled_from(POOL).map(C.SymLit),
)
BIN = ["add", "subtract", "multiply", "divide", "floor-divide", "modulo", "power"]
CMP = ["equal", "less", "less-eq", "greater", "greater-eq", "same", "contains"]


def quoted(e: Any) -> Any:
    """Inside a quote, user names stay unresolved (spec 08): locals and defs become free."""

    def fix(n: Any) -> Any:
        if isinstance(n, C.Name) and n.ref.kind in ("local", "def"):
            return C.Name(n.name, C.Ref("free", n.name))
        return n

    return transform(e, fix)


TYPES = st.recursive(
    st.sampled_from(["number", "integer", "text", "truth", "symbol", "Box"]).map(C.TName),
    lambda t: st.one_of(
        t.map(lambda x: C.TApply("list", (x,))),
        st.tuples(t, t).map(lambda p: C.TApply("map", p)),
        t.map(lambda x: make_union([x, C.TName("nothing")])),
        st.tuples(t, t).map(lambda p: make_union(list(p))),
    ),
    max_leaves=4,
).filter(lambda t: not isinstance(t, C.TOptional) or not isinstance(t.type, C.TUnion))


def interp(parts: list[Any]) -> Any:
    merged: list[Any] = []
    for p in parts:
        if isinstance(p, str) and merged and isinstance(merged[-1], str):
            merged[-1] += p
        elif p != "":
            merged.append(p)
    if all(isinstance(p, str) for p in merged):
        return C.Lit("text", "".join(merged))
    return C.Interp(tuple(merged))


def extend(sub: Any) -> Any:
    return st.one_of(
        st.lists(st.one_of(TEXTS, sub), min_size=1, max_size=4).map(interp),
        st.lists(sub, min_size=1, max_size=4).map(lambda xs: C.SetLit(tuple(xs))),
        st.lists(st.tuples(sub, sub), max_size=3).map(lambda ps: C.MapLit(tuple(ps))),
        st.tuples(sub, TYPES).map(lambda t: C.TypeTest(t[0], t[1])),
        TYPES.map(C.TypeExpr),
        st.tuples(st.sampled_from(BIN), sub, sub).map(lambda t: b(t[0], [t[1], t[2]])),
        sub.map(lambda e: b("negate", [e])),
        st.tuples(st.sampled_from(CMP), sub, sub).map(lambda t: b(t[0], [t[1], t[2]])),
        sub.map(lambda e: b("not", [e])),
        st.tuples(st.sampled_from(["and", "or", "default"]), sub, sub).map(lambda t: b(t[0], [t[1], thunk(t[2])])),
        st.lists(sub, max_size=5).map(lambda xs: C.ListLit(tuple(xs))),
        st.tuples(sub, st.sampled_from(POOL), st.booleans()).map(lambda t: C.Get(t[0], t[1], t[2])),
        st.tuples(sub, sub, st.booleans()).map(lambda t: C.Index(t[0], t[1], t[2])),
        st.tuples(sub, sub, sub).map(lambda t: b("between", [t[0], t[1], t[2]])),
        sub.map(lambda e: C.Call(C.Name("g", C.Ref("def", "g")), (e,))),
        st.tuples(sub, sub).map(lambda t: b("join", [t[0], t[1]])),
        sub.map(lambda e: C.Quote(quoted(e))),
        sub.map(lambda e: C.Try(e)),
        st.tuples(sub, sub).map(lambda t: b("range", [t[0], t[1]])),
    )


EXPRS = st.recursive(LEAVES, extend, max_leaves=12)


def with_expr(e: Any) -> C.Module:
    f = BASE.body[2]
    bind = replace(f.body.stmts[0], value=e)
    body = replace(f.body, stmts=(bind,) + f.body.stmts[1:])
    return replace(BASE, body=(*BASE.body[:2], replace(f, body=body)))


def valid_index(e: Any) -> bool:
    return not any(isinstance(n, C.Index) and n.index == C.Lit("integer", 0) for n in C.walk(e))


def check_laws(m: C.Module) -> None:
    for surface in ("words", "symbols"):
        text = print_module(m, surface)
        again = parse(text, name="rt")
        assert again == m, f"L1/L2 ({surface}):\n{text}"
        assert print_module(again, surface) == text, "L3: formatting is not idempotent"
        assert hash_module(again)[1] == hash_module(m)[1], "L5"


SETTINGS = settings(max_examples=EXAMPLES, deadline=None, suppress_health_check=[HealthCheck.too_slow])


@SETTINGS
@given(EXPRS)
def test_rt_l1_l2_l3_l5_generated(e: Any) -> None:
    if valid_index(e):
        check_laws(with_expr(e))


def corpus() -> list[Path]:
    files = [*sorted((ROOT / "tests" / "corpus").glob("*.say")), *sorted((ROOT / "prelude").glob("*.say"))]
    return files + sorted((ROOT / "tests" / "roundtrip" / "regressions").glob("*.say"))


@pytest.mark.parametrize("path", corpus(), ids=lambda p: p.name)
def test_rt_corpus_l3_l4_l5(path: Path) -> None:
    src = path.read_text(encoding="utf-8")
    m = parse(src, name=path.stem)
    for surface in ("words", "symbols"):
        once = print_module(m, surface, list(lex(src).comments))
        m2 = parse(once, name=path.stem)
        assert m2 == m, f"L4 ({surface})"
        assert print_module(m2, surface, list(lex(once).comments)) == once, f"L3 ({surface})"
        assert hash_module(m2)[1] == hash_module(m)[1], "L5"


def test_rt_mut_breaking_operator_table_fails_a_law(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(P.SYM_OF, "add", "-")
    m = with_expr(b("add", [C.Name("x", C.Ref("local", 0)), C.Lit("integer", 1)]))
    with pytest.raises(AssertionError):
        check_laws(m)
