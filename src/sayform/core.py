"""Core AST: the 44 tagged nodes and 18 tagged sub-nodes (spec/04-core-ast.md section 2).

Every node is a frozen, slotted dataclass whose fields follow catalogue order (which is
also SCS-1 serialisation order). `line` is source-span trivia: it is excluded from
equality, hashing and serialisation (spec 04 section 1: spans live outside the core).
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from decimal import Decimal
from fractions import Fraction
from typing import Any, ClassVar

V0_1_TAGS = frozenset({6, 7, 8, 11})


@dataclass(frozen=True, slots=True)
class Node:
    TAG: ClassVar[int] = 0
    line: int = field(default=0, compare=False, repr=False, kw_only=True)


def tagged(tag: int) -> Any:
    def deco(cls: type) -> type:
        cls.TAG = tag  # type: ignore[attr-defined]
        return cls

    return deco


# ---- structures (no tag) ------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class Ref:
    """Name.ref: kind in local, def, builtin, foreign, patvar, scc, free (unresolved)."""

    kind: str
    value: Any


@dataclass(frozen=True, slots=True)
class Param:
    name: str
    slot: str | None = None
    type: Any = None
    default: Any = None


@dataclass(frozen=True, slots=True)
class TParam:
    name: str
    role: str | None = None


@dataclass(frozen=True, slots=True)
class FieldDef:
    name: str
    type: Any
    default: Any = None


@dataclass(frozen=True, slots=True)
class CaseDef:
    name: str
    fields: tuple[FieldDef, ...] = ()


@dataclass(frozen=True, slots=True)
class Narrow:
    kind: str  # limited-to | read-only
    arg: Any = None


@dataclass(frozen=True, slots=True)
class EffItem:
    effect: str
    narrowing: tuple[Narrow, ...] = ()


@dataclass(frozen=True, slots=True)
class Child:
    label: str | None
    body: Any  # Expr or Block


@dataclass(frozen=True, slots=True)
class Branch:
    cond: Any
    body: Any


@dataclass(frozen=True, slots=True)
class MCase:
    pattern: Any
    guard: Any
    body: Any


# ---- family M ------------------------------------------------------------------------
@tagged(1)
@dataclass(frozen=True, slots=True)
class Module(Node):
    name: str
    edition: int
    uses: tuple[Any, ...]
    needs: tuple[EffItem, ...]
    dialects: tuple[str, ...]
    body: tuple[Any, ...]
    trivia: tuple[Any, ...] = field(default=(), compare=False, repr=False)
    has_header: bool = field(default=True, compare=False, repr=False)


@tagged(2)
@dataclass(frozen=True, slots=True)
class Use(Node):
    path: str
    names: tuple[str, ...] | None = None
    alias: str | None = None
    foreign: str | None = None


@tagged(3)
@dataclass(frozen=True, slots=True)
class Func(Node):
    name: str
    params: tuple[Param, ...]
    result: Any
    effects: tuple[EffItem, ...]
    fails: tuple[str, ...]
    generics: tuple[TParam, ...]
    body: Any


@tagged(4)
@dataclass(frozen=True, slots=True)
class RecordDef(Node):
    name: str
    plural: str
    tparams: tuple[TParam, ...]
    fields: tuple[FieldDef, ...]
    invariants: tuple[Any, ...]
    changeable: bool
    plural_declared: bool = field(default=False, compare=False, repr=False)


@tagged(5)
@dataclass(frozen=True, slots=True)
class VariantDef(Node):
    name: str
    plural: str
    tparams: tuple[TParam, ...]
    cases: tuple[CaseDef, ...]
    plural_declared: bool = field(default=False, compare=False, repr=False)


@tagged(6)
@dataclass(frozen=True, slots=True)
class RoleDef(Node):
    name: str
    tparams: tuple[TParam, ...] = ()
    requires: tuple[Any, ...] = ()
    laws: tuple[str, ...] = ()


@tagged(7)
@dataclass(frozen=True, slots=True)
class Plays(Node):
    type: Any
    role: str
    methods: tuple[Any, ...] = ()


@tagged(8)
@dataclass(frozen=True, slots=True)
class EffectDef(Node):
    name: str
    narrowings: tuple[str, ...] = ()


@tagged(9)
@dataclass(frozen=True, slots=True)
class Ruleset(Node):
    name: str
    rules: tuple[Any, ...]


@tagged(10)
@dataclass(frozen=True, slots=True)
class Rule(Node):
    lhs: Any
    rhs: Any
    guard: Any = None


@tagged(11)
@dataclass(frozen=True, slots=True)
class OperatorDef(Node):
    word: str
    symbol: str | None = None
    arity: int = 2
    prec: tuple[str, str] = ("like", "times")
    assoc: str = "left"
    means: str = ""


@tagged(12)
@dataclass(frozen=True, slots=True)
class Check(Node):
    label: str | None
    subject: Any
    relation: str
    expected: Any = None
    body: Any = None


# ---- family S ------------------------------------------------------------------------
@tagged(13)
@dataclass(frozen=True, slots=True)
class Bind(Node):
    target: Any
    value: Any
    mutable: bool = False
    type: Any = None


@tagged(14)
@dataclass(frozen=True, slots=True)
class Rebind(Node):
    name: Any  # a Name node (its ref identifies the binding)
    value: Any


@tagged(15)
@dataclass(frozen=True, slots=True)
class SetField(Node):
    target: Any
    field: str
    value: Any


@tagged(16)
@dataclass(frozen=True, slots=True)
class If(Node):
    branches: tuple[Branch, ...]
    else_: Any = None


@tagged(17)
@dataclass(frozen=True, slots=True)
class Match(Node):
    subject: Any
    cases: tuple[MCase, ...]
    else_: Any = None


@tagged(18)
@dataclass(frozen=True, slots=True)
class For(Node):
    binder: Any
    source: Any
    body: Any


@tagged(19)
@dataclass(frozen=True, slots=True)
class While(Node):
    cond: Any
    body: Any


@tagged(20)
@dataclass(frozen=True, slots=True)
class Stop(Node):
    pass


@tagged(21)
@dataclass(frozen=True, slots=True)
class Skip(Node):
    pass


@tagged(22)
@dataclass(frozen=True, slots=True)
class Return(Node):
    value: Any = None


@tagged(23)
@dataclass(frozen=True, slots=True)
class ExprStmt(Node):
    expr: Any


@tagged(24)
@dataclass(frozen=True, slots=True)
class WithCap(Node):
    cap: Any
    narrowing: tuple[Narrow, ...]
    body: Any


@tagged(25)
@dataclass(frozen=True, slots=True)
class Concurrent(Node):
    mode: str
    children: tuple[Child, ...]


@tagged(26)
@dataclass(frozen=True, slots=True)
class Within(Node):
    limit: Any
    body: Any


@tagged(27)
@dataclass(frozen=True, slots=True)
class Block(Node):
    stmts: tuple[Any, ...]
    trivia: tuple[Any, ...] = field(default=(), compare=False, repr=False)


# ---- family E ------------------------------------------------------------------------
def lit_key(kind: str, value: Any) -> Any:
    """Equality key for literal values: keeps decimal scale and the sign of approx zero."""
    if kind == "decimal" and isinstance(value, Decimal):
        return value.as_tuple()
    if kind == "approx":
        return repr(float(value))
    if kind == "quantity":
        n, unit = value
        return (lit_key("decimal" if isinstance(n, Decimal) else "integer", n), unit)
    if kind == "rational" and isinstance(value, Fraction):
        return (value.numerator, value.denominator)
    return value


@tagged(28)
@dataclass(frozen=True, slots=True, eq=False)
class Lit(Node):
    kind: str
    value: Any

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, Lit)
            and self.kind == other.kind
            and lit_key(self.kind, self.value) == lit_key(other.kind, other.value)
        )

    def __hash__(self) -> int:
        return hash((self.kind, lit_key(self.kind, self.value)))


@tagged(29)
@dataclass(frozen=True, slots=True)
class Interp(Node):
    parts: tuple[Any, ...]


@tagged(30)
@dataclass(frozen=True, slots=True)
class SymLit(Node):
    name: str


@tagged(31)
@dataclass(frozen=True, slots=True)
class Name(Node):
    name: str
    ref: Ref


@tagged(32)
@dataclass(frozen=True, slots=True)
class Get(Node):
    target: Any
    field: str
    optional: bool = False


@tagged(33)
@dataclass(frozen=True, slots=True)
class Index(Node):
    target: Any
    index: Any
    optional: bool = False


@tagged(34)
@dataclass(frozen=True, slots=True)
class Call(Node):
    fn: Any
    args: tuple[Any, ...] = ()
    slots: tuple[tuple[str, Any], ...] = ()


@tagged(35)
@dataclass(frozen=True, slots=True)
class Lambda(Node):
    params: tuple[Param, ...]
    body: Any


@tagged(36)
@dataclass(frozen=True, slots=True)
class ListLit(Node):
    items: tuple[Any, ...]


@tagged(37)
@dataclass(frozen=True, slots=True)
class MapLit(Node):
    pairs: tuple[tuple[Any, Any], ...]


@tagged(38)
@dataclass(frozen=True, slots=True)
class SetLit(Node):
    items: tuple[Any, ...]


@tagged(39)
@dataclass(frozen=True, slots=True)
class RecordLit(Node):
    type: Any
    fields: tuple[tuple[str, Any], ...]
    base: Any = None


@tagged(40)
@dataclass(frozen=True, slots=True)
class TypeTest(Node):
    value: Any
    type: Any


@tagged(41)
@dataclass(frozen=True, slots=True)
class Try(Node):
    expr: Any


@tagged(42)
@dataclass(frozen=True, slots=True)
class Quote(Node):
    expr: Any


@tagged(43)
@dataclass(frozen=True, slots=True)
class Unquote(Node):
    expr: Any


@tagged(44)
@dataclass(frozen=True, slots=True)
class TypeExpr(Node):
    type: Any


# ---- types (60-68) -----------------------------------------------------------------
@tagged(60)
@dataclass(frozen=True, slots=True)
class TName(Node):
    ref: str  # builtin type word (lowercase) or a user type name


@tagged(61)
@dataclass(frozen=True, slots=True)
class TApply(Node):
    head: str  # list | set | map | channel
    args: tuple[Any, ...]


@tagged(62)
@dataclass(frozen=True, slots=True)
class TOptional(Node):
    type: Any


@tagged(63)
@dataclass(frozen=True, slots=True)
class TUnion(Node):
    types: tuple[Any, ...]


@tagged(64)
@dataclass(frozen=True, slots=True)
class TVar(Node):
    name: str


@tagged(65)
@dataclass(frozen=True, slots=True)
class TFunc(Node):
    params: tuple[Any, ...]
    result: Any
    effects: tuple[EffItem, ...] = ()
    fails: tuple[str, ...] = ()


@tagged(66)
@dataclass(frozen=True, slots=True)
class TQuantity(Node):
    dimension: str


@tagged(67)
@dataclass(frozen=True, slots=True)
class TMoney(Node):
    currency: str | None = None


@tagged(68)
@dataclass(frozen=True, slots=True)
class TAnything(Node):
    pass


# ---- patterns (70-78) --------------------------------------------------------------
@tagged(70)
@dataclass(frozen=True, slots=True)
class PBind(Node):
    name: str
    type: Any = None
    ref: Ref | None = None


@tagged(71)
@dataclass(frozen=True, slots=True)
class PWild(Node):
    pass


@tagged(72)
@dataclass(frozen=True, slots=True)
class PLit(Node):
    lit: Any


@tagged(73)
@dataclass(frozen=True, slots=True)
class PRecord(Node):
    type: Any
    fields: tuple[tuple[str, Any], ...]
    open: bool = False


@tagged(74)
@dataclass(frozen=True, slots=True)
class PCase(Node):
    case: str
    fields: tuple[tuple[str, Any], ...] = ()
    open: bool = False


@tagged(75)
@dataclass(frozen=True, slots=True)
class PList(Node):
    prefix: tuple[Any, ...]
    rest: Any = None


@tagged(76)
@dataclass(frozen=True, slots=True)
class PRange(Node):
    lo: Any
    hi: Any
    inclusive: bool = True


@tagged(77)
@dataclass(frozen=True, slots=True)
class PAlt(Node):
    alts: tuple[Any, ...]


@tagged(78)
@dataclass(frozen=True, slots=True)
class PQuote(Node):
    expr: Any


CORE_NODES: tuple[type[Node], ...] = tuple(
    c
    for c in list(globals().values())
    if isinstance(c, type) and issubclass(c, Node) and 1 <= getattr(c, "TAG", 0) <= 44
)
TYPE_NODES: tuple[type[Node], ...] = tuple(
    c
    for c in list(globals().values())
    if isinstance(c, type) and issubclass(c, Node) and 60 <= getattr(c, "TAG", 0) <= 68
)
PATTERN_NODES: tuple[type[Node], ...] = tuple(
    c
    for c in list(globals().values())
    if isinstance(c, type) and issubclass(c, Node) and 70 <= getattr(c, "TAG", 0) <= 78
)
BY_TAG: dict[int, type[Node]] = {c.TAG: c for c in CORE_NODES + TYPE_NODES + PATTERN_NODES}
EXPR_NODES = tuple(c for c in CORE_NODES if 28 <= c.TAG <= 44)
STRUCTS = (Ref, Param, TParam, FieldDef, CaseDef, Narrow, EffItem, Child, Branch, MCase)


def node_fields(n: Any) -> list[str]:
    return [f.name for f in fields(n) if f.compare]


def walk(n: Any) -> Any:
    """Yield every node and structure in a core tree (pre-order)."""
    stack = [n]
    while stack:
        x = stack.pop()
        if isinstance(x, (tuple, list)):
            stack.extend(reversed(x))
        elif isinstance(x, Node) or isinstance(x, STRUCTS):
            yield x
            stack.extend(reversed([getattr(x, f) for f in node_fields(x)]))


def nothing_lit() -> Lit:
    return Lit("nothing", None)
