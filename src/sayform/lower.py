"""Lowering tables: operators, builtin signatures and effects (spec/04-core-ast.md section 3,
spec/06-operators.md, spec/12-stdlib.md).

Operators lower to `Call(Name(op, Builtin(op)), ...)`; the printers use the reverse tables.
"""

from __future__ import annotations

from typing import Any

from .core import Call, Lambda, Name, Ref

#: symbols operator -> builtin; words operator -> builtin (P8-P12)
SYM_BINOPS = {
    "+": "add", "-": "subtract", "*": "multiply", "/": "divide", "//": "floor-divide",
    "%": "modulo", "^": "power", "++": "join",
}  # fmt: skip
WORD_BINOPS = {"plus": "add", "minus": "subtract", "times": "multiply", "mod": "modulo"}
BINOP_PREC = {
    "add": 9, "subtract": 9, "multiply": 10, "divide": 10, "floor-divide": 10,
    "modulo": 10, "power": 12,
}  # fmt: skip
SYM_OF = {v: k for k, v in SYM_BINOPS.items()}
WORDS_OF = {
    "add": "plus",
    "subtract": "minus",
    "multiply": "times",
    "divide": "divided by",
    "floor-divide": "divided by",
    "modulo": "mod",
    "power": "to the power of",
}
CMP_SYM = {
    "=": "equal",
    "==": "equal",
    "<": "less",
    "<=": "less-eq",
    ">": "greater",
    ">=": "greater-eq",
    "===": "same",
}
CMP_WORDS = {
    "less": "is less than",
    "less-eq": "is at most",
    "greater": "is greater than",
    "greater-eq": "is at least",
    "equal": "equals",
    "same": "is the same as",
}
CMP_SYM_OUT = {
    "equal": "=",
    "less": "<",
    "less-eq": "<=",
    "greater": ">",
    "greater-eq": ">=",
    "same": "===",
}
CLAUSE_FNS = frozenset({"filter", "map", "sort", "sort-by", "group-by", "join", "join-all"})

#: Precedence ladder P0-P15 (spec 03 section 3); P13 is reserved.
PRECEDENCE: tuple[str, ...] = (
    "statements", "pipeline", "absence", "or", "and", "not", "comparison",
    "postfix clauses", "range", "additive", "multiplicative", "unary", "power",
    "(reserved)", "application", "primary",
)  # fmt: skip

# Builtin signatures: name -> list of (lead, param, has_default). Lead None = positional;
# "of" = first-parameter lead; slot words; "with" = named. (spec 12 section 2)
P = None
HOST_SIGS: dict[str, list[tuple[str | None, str, bool]]] = {
    "equal": [(P, "a", False), (P, "b", False)],
    "same": [(P, "a", False), (P, "b", False)],
    "not": [("of", "a", False)],
    "and": [(P, "a", False), (P, "b", False)],
    "or": [(P, "a", False), (P, "b", False)],
    "default": [(P, "a", False), (P, "b", False)],
    "problem": [(P, "kind", False), ("with", "message", True), ("with", "data", True)],
    "display": [("of", "value", False)],
    "show": [(P, "value", False)],
    "ask": [(P, "prompt", False)],
    "add": [(P, "a", False), (P, "b", False)],
    "subtract": [(P, "a", False), (P, "b", False)],
    "multiply": [(P, "a", False), (P, "b", False)],
    "divide": [(P, "a", False), (P, "b", False)],
    "floor-divide": [(P, "a", False), (P, "b", False)],
    "modulo": [(P, "a", False), (P, "b", False)],
    "power": [(P, "a", False), (P, "b", False)],
    "negate": [("of", "a", False)],
    "less": [(P, "a", False), (P, "b", False)],
    "round": [(P, "x", False), ("with", "places", True), ("with", "mode", True)],
    "length": [("of", "t", False)],
    "uppercase": [("of", "t", False)],
    "lowercase": [("of", "t", False)],
    "join": [(P, "a", False), (P, "b", False)],
    "split": [(P, "t", False), ("by", "separator", False)],
    "trim": [(P, "t", False)],
    "code-points": [("of", "t", False)],
    "utf8-bytes": [("of", "t", False)],
    "parse-number": [(P, "t", False)],
    "range": [
        (P, "a", False),
        (P, "b", False),
        ("with", "exclusive", True),
        ("with", "step", True),
    ],
    "added": [(P, "c", False), (P, "item", False)],
    "count": [("of", "c", False)],
    "sort-by": [("of", "c", False), (P, "key", False), ("with", "descending", True)],
    "contains": [(P, "c", False), (P, "x", False)],
    "keys": [("of", "m", False)],
    "values": [("of", "m", False)],
    "evaluate": [("of", "e", False), ("with", "bindings", True)],
    "match": [(P, "e", False), (P, "pattern", False)],
    "egraph-simplify": [
        (P, "e", False),
        (P, "rules", False),
        ("with", "nodes", True),
        ("with", "steps", True),
    ],
    "egraph-equiv": [(P, "a", False), (P, "b", False), (P, "rules", False)],
    "head": [("of", "e", False)],
    "arguments": [("of", "e", False)],
    "new-channel": [("with", "capacity", True)],
    "send": [(P, "value", False), ("into", "ch", False)],
    "receive": [("from", "ch", False)],
    "close": [(P, "ch", False)],
    "sleep": [("for", "d", False)],
    "map-concurrent": [("of", "c", False), (P, "f", False)],
    "received": [("of", "ch", False)],
    "files.read-text": [(P, "path", False)],
    "files.write-text": [(P, "content", False), ("to", "path", False)],
    "clock.now": [],
    "random.random-integer": [("from", "low", False), ("to", "high", False)],
}
PRELUDE_NAMES: tuple[str, ...] = (
    "less-eq", "greater", "greater-eq", "between", "absolute", "checked-divide", "join-all",
    "map", "filter", "sort", "first", "last", "take", "drop", "sum", "group-by", "zip",
    "is-empty", "reversed", "largest", "smallest",
)  # fmt: skip
PRELUDE_EXTRAS = ("Pair", "empty-set")
#: Signatures of prelude functions that take slot or named arguments (spec 12 section 3).
PRELUDE_SIGS: dict[str, list[tuple[str | None, str, bool]]] = {
    "between": [
        (P, "x", False),
        (P, "lo", False),
        (P, "hi", False),
        ("with", "low-inclusive", True),
        ("with", "high-inclusive", True),
    ],
    "checked-divide": [(P, "a", False), ("by", "b", False)],
    "take": [(P, "n", False), ("from", "c", False)],
    "drop": [(P, "n", False), ("from", "c", False)],
}
BUILTIN_NAMES = frozenset(HOST_SIGS) | frozenset(PRELUDE_NAMES) | frozenset(PRELUDE_EXTRAS)
HOST_MODULES = frozenset({"files", "clock", "random"})
BUILTIN_EFFECTS: dict[str, str] = {
    "show": "console", "ask": "console",
    "new-channel": "tasks", "send": "tasks", "receive": "tasks", "close": "tasks",
    "sleep": "tasks", "map-concurrent": "tasks", "received": "tasks",
    "files.read-text": "files", "files.write-text": "files", "clock.now": "clock",
    "random.random-integer": "random",
}  # fmt: skip
BUILTIN_FAILS: dict[str, tuple[str, ...]] = {
    "ask": ("not-found",), "parse-number": ("parse-error",), "evaluate": ("not-found",),
    "files.read-text": ("not-found",), "checked-divide": ("division-by-zero",),
}  # fmt: skip


def bname(name: str, line: int = 0) -> Name:
    return Name(name, Ref("builtin", name), line=line)


def op_call(fn: str, args: list[Any], line: int = 0, slots: tuple[tuple[str, Any], ...] = ()) -> Call:
    return Call(bname(fn, line), tuple(args), slots, line=line)


def thunk(e: Any) -> Lambda:
    return Lambda((), e, line=getattr(e, "line", 0))


def is_op(n: Any, *names: str) -> bool:
    return isinstance(n, Call) and isinstance(n.fn, Name) and n.fn.ref.kind == "builtin" and n.fn.name in names
