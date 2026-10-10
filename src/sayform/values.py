"""Runtime values, numbers, equality, ordering, type tests and `display` (spec/05-types-values.md).

Representation: nothing=None, Truth=bool, Integer=int, Decimal=decimal.Decimal, Rational=
fractions.Fraction, Approx=float, Text=str, List=tuple, Map=MapV, Set=SetV; other kinds below.
"""

from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass, field
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Context, Decimal
from fractions import Fraction
from typing import Any

from . import core as C
from .diagnostics import panic

EXACT = Context(prec=100_000, Emax=10**9, Emin=-(10**9))


@dataclass(frozen=True, slots=True)
class Sym:
    """An interned symbol; `-` and `_` spellings are the same symbol (SYM-01)."""

    name: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", self.name.replace("_", "-"))


@dataclass(frozen=True, slots=True)
class Quantity:
    """A time quantity (core supports only the time dimension), stored in milliseconds."""

    ms: Any
    unit: str = "ms"


UNIT_MS = {"ms": 1, "s": 1000, "min": 60000, "h": 3600000}


class MapV(dict[Any, Any]):
    """Insertion-ordered immutable map; equality ignores order."""

    def __hash__(self) -> int:  # type: ignore[override]
        return hash(frozenset((k, hk(v)) for k, v in self.items()))


class SetV(tuple[Any, ...]):
    """Insertion-ordered immutable set; equality ignores order."""

    def __eq__(self, other: object) -> bool:
        return isinstance(other, SetV) and len(self) == len(other) and all(contains(other, x) for x in self)

    def __hash__(self) -> int:
        return hash(frozenset(hk(x) for x in self))


def hk(v: Any) -> Any:
    try:
        hash(v)
        return v
    except TypeError:
        return id(v)


@dataclass(eq=False, slots=True)
class Record:
    """A record or variant-case value. `tname` is the record type or the variant type."""

    tname: str
    fields: dict[str, Any]
    case: str | None = None
    changeable: bool = False

    def __eq__(self, o: object) -> bool:
        return (
            isinstance(o, Record) and (self.tname, self.case) == (o.tname, o.case) and equal_map(self.fields, o.fields)
        )

    def __hash__(self) -> int:
        return hash((self.tname, self.case, tuple(hk(v) for v in self.fields.values())))


@dataclass(frozen=True, slots=True)
class Problem:
    kind: Sym
    message: str = ""
    data: Any = field(default_factory=MapV)


@dataclass(frozen=True, slots=True)
class ExprV:
    """An Expression value: an immutable expression-family core tree (spec 08)."""

    node: Any


@dataclass(frozen=True, slots=True)
class TypeV:
    type: Any


def is_num(v: Any) -> bool:
    return isinstance(v, (int, Decimal, Fraction, float)) and not isinstance(v, bool)


def exact(v: Any) -> bool:
    return is_num(v) and not isinstance(v, float)


def kind(v: Any) -> str:
    """Words name of a value's type, used in messages."""
    if v is None:
        return "nothing"
    if isinstance(v, bool):
        return "a truth"
    names = {int: "an integer", Decimal: "a decimal", Fraction: "a rational", float: "an approx", str: "text"}
    for t, n in names.items():
        if type(v) is t:
            return n
    if isinstance(v, Record):
        return f"a {v.tname}"
    other = {
        tuple: "a list",
        MapV: "a map",
        SetV: "a set",
        Sym: "a symbol",
        Problem: "a problem",
        ExprV: "an expression",
    }
    for t, n in other.items():
        if isinstance(v, t):
            return n
    return "a " + type(v).__name__.lower()


def mismatch(
    op: str, *vs: Any, expected: str = "values of a type it accepts", reason: str = "", fix: str = ""
) -> Exception:
    return panic(
        "E0212",
        operation=f"`{op}`",
        actual=" and ".join(kind(v) for v in vs) or "this call",
        expected=expected,
        reason=reason or "Builtins check their argument types at run time",
        fix=fix or "Convert the value first or check its type with `is`",
    )


# ---- numbers (spec 05 section 3) ------------------------------------------------------
def frac(v: Any) -> Fraction:
    return Fraction(v)


def normalise(q: Fraction) -> Any:
    """Integer if whole; else a terminating Decimal with the smallest scale; else Rational."""
    if q.denominator == 1:
        return q.numerator
    d, twos, fives = q.denominator, 0, 0
    while d % 2 == 0:
        d, twos = d // 2, twos + 1
    while d % 5 == 0:
        d, fives = d // 5, fives + 1
    if d != 1:
        return q
    k = max(twos, fives)
    return Decimal(q.numerator * 10**k // q.denominator).scaleb(-k, EXACT)


OPS = {"add": "+", "subtract": "-", "multiply": "*", "divide": "/", "floor-divide": "//", "modulo": "%"}


def arith(op: str, a: Any, b: Any) -> Any:
    if not (is_num(a) and is_num(b)):
        if op == "add" and isinstance(a, Quantity) and isinstance(b, Quantity):
            return Quantity(a.ms + b.ms, a.unit)
        if op == "add" and (isinstance(a, str) or isinstance(b, str)):
            raise panic("E0202", a=display(a, True), op="+", b=display(b, True))
        raise mismatch(op, a, b)
    if isinstance(a, float) or isinstance(b, float):
        x, y = float(a), float(b)
        try:
            r = {"add": x + y, "subtract": x - y, "multiply": x * y}.get(op)
            if r is None:
                if y == 0:
                    raise panic("E0841", a=display(a), op=OPS[op])
                r = x / y if op == "divide" else float(math.floor(x / y)) if op == "floor-divide" else x % y
        except OverflowError:
            raise mismatch(op, a, b) from None
        if isinstance(r, float) and math.isinf(r):
            raise mismatch(
                op, a, b, expected="a finite result", reason="Approx overflow is an error outside `dialect ieee`"
            )
        return r if op != "floor-divide" else int(r)
    if op in ("add", "subtract", "multiply") and not (isinstance(a, Fraction) or isinstance(b, Fraction)):
        if isinstance(a, int) and isinstance(b, int):
            return a + b if op == "add" else a - b if op == "subtract" else a * b
        da, db = Decimal(a), Decimal(b)
        return (
            EXACT.add(da, db) if op == "add" else EXACT.subtract(da, db) if op == "subtract" else EXACT.multiply(da, db)
        )
    p, q = frac(a), frac(b)
    if op in ("add", "subtract", "multiply"):
        return normalise(p + q if op == "add" else p - q if op == "subtract" else p * q)
    if q == 0:
        raise panic("E0841", a=display(a), op=OPS[op])
    if op == "divide":
        return normalise(p / q)
    if op == "floor-divide":
        return math.floor(p / q)
    return normalise(p - q * math.floor(p / q))


def power(a: Any, b: Any) -> Any:
    if not (is_num(a) and is_num(b)):
        raise mismatch("power", a, b)
    if isinstance(b, int) and not isinstance(a, float):
        if a == 0 and b < 0:
            raise panic("E0841", a=display(a), op="^")
        if isinstance(a, int) and b >= 0:
            return a**b
        return normalise(frac(a) ** b)
    if a < 0:
        raise panic("E0842", a=display(a), b=display(b))
    try:
        return float(a) ** float(b)
    except OverflowError:
        raise mismatch("power", a, b) from None


def negate(a: Any) -> Any:
    if isinstance(a, Quantity):
        return Quantity(-a.ms, a.unit)
    if not is_num(a):
        raise mismatch("negate", a)
    return -a if not isinstance(a, Decimal) else EXACT.minus(a)


def round_num(x: Any, places: int = 0, mode: Any = None) -> Any:
    if not is_num(x) or not isinstance(places, int) or isinstance(places, bool):
        raise mismatch("round", x, places)
    up = mode is not None and mode.name == "half-up"
    if isinstance(x, float):
        d = Decimal(repr(x)).quantize(Decimal(1).scaleb(-places), ROUND_HALF_UP if up else ROUND_HALF_EVEN)
        return float(d)
    s = frac(x) * 10**places
    n = math.floor(s + Fraction(1, 2)) if up else round(s)
    if up and s < 0:
        n = -math.floor(-s + Fraction(1, 2))
    return n // 10**places if places <= 0 else Decimal(n).scaleb(-places, EXACT)


# ---- equality and ordering (spec 05 section 7) ------------------------------------------
def equal(a: Any, b: Any) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if is_num(a) or is_num(b):
        return is_num(a) and is_num(b) and a == b
    if isinstance(a, tuple) and not isinstance(a, SetV):
        return type(b) is tuple and len(a) == len(b) and all(equal(x, y) for x, y in zip(a, b, strict=True))
    if isinstance(a, MapV):
        return isinstance(b, MapV) and equal_map(a, b)
    if isinstance(a, Quantity) and isinstance(b, Quantity):
        return bool(a.ms == b.ms)
    return type(a) is type(b) and bool(a == b)


def equal_map(a: dict[Any, Any], b: dict[Any, Any]) -> bool:
    return len(a) == len(b) and all(k in b and equal(v, b[k]) for k, v in a.items())


def contains(c: Any, x: Any) -> bool:
    if isinstance(c, str):
        if not isinstance(x, str):
            raise mismatch("contains", c, x)
        return x in c
    if isinstance(c, (tuple, MapV)):
        return any(equal(y, x) for y in c)
    raise mismatch("contains", c, x)


def less(a: Any, b: Any) -> bool:
    if is_num(a) and is_num(b):
        return bool(a < b)
    if isinstance(a, str) and isinstance(b, str):
        return a < b
    if isinstance(a, Quantity) and isinstance(b, Quantity):
        return bool(a.ms < b.ms)
    raise mismatch("less", a, b)


# ---- type tests (spec 05 section 1) -------------------------------------------------------
BUILTIN_TYPES: dict[str, Any] = {
    "nothing": lambda v: v is None,
    "truth": lambda v: isinstance(v, bool),
    "number": is_num,
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "decimal": lambda v: (isinstance(v, int) and not isinstance(v, bool)) or isinstance(v, Decimal),
    "rational": exact,
    "approx": lambda v: isinstance(v, float),
    "text": lambda v: isinstance(v, str),
    "symbol": lambda v: isinstance(v, Sym),
    "expression": lambda v: isinstance(v, ExprV),
    "problem": lambda v: isinstance(v, Problem),
    "type": lambda v: isinstance(v, TypeV),
    "anything": lambda v: True,
}


def type_test(v: Any, t: Any, variants: dict[str, set[str]] | None = None) -> bool:
    if isinstance(t, (C.TAnything, C.TVar)) or t is None:
        return True
    if isinstance(t, C.TName):
        fn = BUILTIN_TYPES.get(t.ref)
        if fn is not None:
            return bool(fn(v))
        if t.ref == "function":
            return callable(getattr(v, "call", None))
        return isinstance(v, Record) and (v.tname == t.ref or v.case == t.ref)
    if isinstance(t, C.TOptional):
        return v is None or type_test(v, t.type)
    if isinstance(t, C.TUnion):
        return any(type_test(v, x) for x in t.types)
    if isinstance(t, C.TApply):
        if t.head == "list":
            return type(v) is tuple and all(type_test(x, t.args[0]) for x in v)
        if t.head == "set":
            return isinstance(v, SetV) and all(type_test(x, t.args[0]) for x in v)
        if t.head == "map":
            return isinstance(v, MapV) and all(
                type_test(k, t.args[0]) and type_test(x, t.args[1]) for k, x in v.items()
            )
        return type(v).__name__ == "Channel"
    if isinstance(t, C.TFunc):
        return callable(getattr(v, "call", None))
    if isinstance(t, C.TQuantity):
        return isinstance(v, Quantity)
    return False


def specificity(t: Any) -> int:
    """Rank for multiple dispatch: higher is more specific (spec 07 section 8)."""
    if t is None or isinstance(t, (C.TAnything, C.TVar)):
        return 0
    if isinstance(t, (C.TUnion, C.TOptional)):
        return 1
    if isinstance(t, C.TName):
        return {"number": 2, "rational": 3, "decimal": 4, "integer": 5}.get(t.ref, 6)
    return 6


# ---- text (spec 05 section 4) -----------------------------------------------------------
def _gcb(c: str) -> str:
    o = ord(c)
    if c in "\r\n":
        return c
    if c == "\u200d":
        return "ZWJ"
    if 0x1F1E6 <= o <= 0x1F1FF:
        return "RI"
    if 0x1F3FB <= o <= 0x1F3FF or 0xFE00 <= o <= 0xFE0F or 0xE0020 <= o <= 0xE007F:
        return "EXT"
    cat = unicodedata.category(c)
    if cat in ("Mn", "Me"):
        return "EXT"
    if cat == "Mc":
        return "SM"
    if 0x1100 <= o <= 0x115F or 0xA960 <= o <= 0xA97C:
        return "L"
    if 0x1160 <= o <= 0x11A7 or 0xD7B0 <= o <= 0xD7C6:
        return "V"
    if 0x11A8 <= o <= 0x11FF or 0xD7CB <= o <= 0xD7FB:
        return "T"
    if 0xAC00 <= o <= 0xD7A3:
        return "LV" if (o - 0xAC00) % 28 == 0 else "LVT"
    if cat in ("Cc", "Zl", "Zp") or (cat == "Cf" and c != "\u200d"):
        return "CTL"
    if cat == "So" or 0x1F000 <= o <= 0x1FAFF:
        return "PIC"
    return "X"


def graphemes(t: str) -> list[str]:
    """Extended grapheme clusters (UAX #29 rules GB3-GB13 over Python's Unicode tables)."""
    out: list[str] = []
    prev, ri, pic_zwj = "", 0, False
    for c in t:
        k = _gcb(c)
        join = bool(out) and (
            (prev == "\r" and k == "\n")
            or (prev not in ("\r", "\n", "CTL") and k in ("EXT", "ZWJ", "SM"))
            or (prev == "L" and k in ("L", "V", "LV", "LVT"))
            or (prev in ("LV", "V") and k in ("V", "T"))
            or (prev in ("LVT", "T") and k == "T")
            or (prev == "ZWJ" and k == "PIC" and pic_zwj)
            or (prev == "RI" and k == "RI" and ri % 2 == 1)
        )
        if join:
            out[-1] += c
        else:
            out.append(c)
            pic_zwj = False
        if k == "PIC":
            pic_zwj = True
        elif k not in ("EXT", "ZWJ"):
            pic_zwj = False
        ri = ri + 1 if k == "RI" else 0
        prev = k
    return out


# ---- display (spec 12 section 2.1 #8) -----------------------------------------------------
def num_text(v: Any) -> str:
    if isinstance(v, float):
        return "approx " + repr(v)
    if isinstance(v, Decimal):
        return format(v, "f")
    if isinstance(v, Fraction):
        return f"{v.numerator}/{v.denominator}"
    return str(v)


def display(v: Any, nested: bool = False) -> str:
    from .printer import escape_text, expr_text

    if v is None:
        return "nothing"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if is_num(v):
        return num_text(v)
    if isinstance(v, str):
        return f'"{escape_text(v)}"' if nested else v
    if isinstance(v, Sym):
        return "'" + v.name
    if isinstance(v, SetV):
        return "{" + ", ".join(display(x, True) for x in v) + "}" if v else "empty-set"
    if isinstance(v, tuple):
        return "[" + ", ".join(display(x, True) for x in v) + "]"
    if isinstance(v, MapV):
        return "{" + ", ".join(f"{display(k, True)}: {display(x, True)}" for k, x in v.items()) + "}"
    if isinstance(v, Record):
        head = v.case or v.tname
        parts = [f"{k} {display(x, True)}" for k, x in v.fields.items()]
        return head + (" with " + " and ".join(parts) if parts else "")
    if isinstance(v, Problem):
        return f"problem {v.kind.name}" + (f": {v.message}" if v.message else "")
    if isinstance(v, ExprV):
        return expr_text(v.node)
    if isinstance(v, TypeV):
        return expr_text(C.TypeExpr(v.type))
    if isinstance(v, Quantity):
        n = normalise(frac(v.ms) / UNIT_MS[v.unit])
        return f"{num_text(n)}{v.unit}"
    name = getattr(v, "name", None)
    return f"function {name}" if name else type(v).__name__.lower()
