"""Words and symbols printers for the core (spec/04-core-ast.md section 4, spec/13-tooling.md
section 2). `print_module(m, "words" | "symbols")` returns canonical source; parsing it gives
back the same core (laws L1, L2).

Expressions print as `Out(text, prec, open)`: `prec` is the ladder level P1-P15 of the
printed form; `open` marks words forms that end in a greedy argument (prefix calls,
`given …`, `from a to b`, `Person with …`), which must be bracketed before an operator,
clause or further argument (rules R6, R7, F-R8).
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any, NamedTuple

from . import core as C
from .keywords import CONTEXTUAL_SET, RESERVED_SET, SLOT_WORDS
from .lower import BUILTIN_NAMES, CMP_SYM_OUT, CMP_WORDS, HOST_SIGS, PRELUDE_SIGS, SYM_OF, WORDS_OF

UNIT_WORDS = {"ms": "milliseconds", "s": "seconds", "min": "minutes"}
TYPE_SYM = {"number": "Number", "integer": "Integer", "decimal": "Decimal", "rational": "Rational",
            "approx": "Approx", "truth": "Truth", "symbol": "Symbol", "expression": "Expression",
            "problem": "Problem", "type": "Type", "capability": "Capability", "text": "Text",
            "nothing": "Nothing"}  # fmt: skip
HEAD_SYM = {"list": "List", "set": "Set", "map": "Map", "channel": "Channel"}
MASS = {"text", "nothing", "anything"}
CLAUSES = {"filter", "map", "sort", "sort-by", "group-by", "join", "join-all"}
CMP_FNS = {"equal", "less", "less-eq", "greater", "greater-eq", "same"}


class Out(NamedTuple):
    text: str
    prec: int
    open: bool = False


def escape_text(s: str) -> str:
    """F-R9: minimal re-escaping."""
    out = []
    for ch in s:
        if ch in '"\\{}':
            out.append("\\" + ch)
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\t":
            out.append("\\t")
        elif ord(ch) < 0x20 or 0x7F <= ord(ch) < 0xA0:
            out.append(f"\\u{{{ord(ch):X}}}")
        else:
            out.append(ch)
    return "".join(out)


def article(word: str) -> str:
    w = word.lower()
    if w.startswith(("uni", "use", "url", "uuid", "one")):
        return "a"
    if w.startswith(("hour", "honest", "honour")):
        return "an"
    return "an" if w[:1] in "aeiou" else "a"


def plural_of(name: str) -> str:
    low = name[0].lower() + name[1:] if name[:1].isupper() else name
    return low + ("es" if low.endswith(("s", "x", "z", "ch", "sh")) else "s")


class Printer:
    def __init__(self, surface: str, mod: C.Module | None = None, comments: list[Any] | None = None) -> None:
        self.w = surface == "words"
        self.sigs: dict[str, list[tuple[str | None, str, bool]]] = {**HOST_SIGS, **PRELUDE_SIGS}
        self.defs: dict[str, str] = {}
        self.plurals: dict[str, str] = {}
        self.fields: set[str] = set()
        self.comments = sorted(comments or [], key=lambda c: (c[0], c[1]))
        self.locals: list[set[str]] = [set()]
        self.it_depth: list[int] = []
        self.quote = 0
        if mod is not None:
            self.index(mod)

    def index(self, mod: C.Module) -> None:
        for d in mod.body:
            if isinstance(d, C.Func):
                self.defs[d.name] = "func"
                self.sigs[d.name] = [(p.slot, p.name, p.default is not None) for p in d.params]
            elif isinstance(d, C.RecordDef):
                self.defs[d.name] = "record"
                self.plurals[d.name] = d.plural
                self.fields |= {f.name for f in d.fields}
            elif isinstance(d, C.VariantDef):
                self.defs[d.name] = "variant"
                self.plurals[d.name] = d.plural
                for c in d.cases:
                    self.defs[c.name] = "case"
                    self.fields |= {f.name for f in c.fields}
            elif isinstance(d, C.Bind):
                for n in pattern_names(d.target):
                    self.defs[n] = "const"

    # ---- names -------------------------------------------------------------------------
    def nm(self, name: str) -> str:
        return name if self.w else name.replace("-", "_")

    def is_local(self, name: str) -> bool:
        return any(name in s for s in self.locals)

    # ---- expressions -------------------------------------------------------------------
    def ex(self, n: Any, prec: int = 1, cond: bool = False) -> str:
        """Print `n` so that it parses back at a context needing level >= `prec`."""
        o = self.out(n, cond)
        if o.prec < prec or (cond and o.prec == 7):
            return f"({o.text})"
        return o.text

    def closed(self, n: Any, prec: int) -> str:
        o = self.out(n)
        return f"({o.text})" if o.prec < prec or o.open else o.text

    def post(self, n: Any) -> str:
        """A postfix target (`x.f`, `x[i]`, `x?`, `x's f`): numbers are bracketed (`(0).f`)."""
        o = self.out(n)
        num = isinstance(n, C.Lit) and n.kind in ("integer", "decimal", "approx", "quantity")
        num = num or isinstance(n, C.TypeExpr)
        return f"({o.text})" if o.prec < 14 or o.open or num or o.text.endswith("?") else o.text

    def out(self, n: Any, cond: bool = False) -> Out:
        meth = getattr(self, "e_" + type(n).__name__, None)
        if meth is None:
            return Out(f"<{type(n).__name__}>", 15)
        res: Out = meth(n) if type(n).__name__ != "Call" else self.e_Call(n, cond)
        return res

    def e_Lit(self, n: C.Lit) -> Out:
        k, v = n.kind, n.value
        if k == "text":
            return Out(f'"{escape_text(v)}"', 15)
        if k == "truth":
            return Out("yes" if v else "no", 15)
        if k == "nothing":
            return Out("nothing", 15)
        if k == "approx":
            return Out(f"approx {float(v)!r}".replace("inf", "inf"), 15)
        if k == "quantity":
            num, unit = v
            text = f"{num} {UNIT_WORDS[unit]}" if self.w else f"{num}{unit}"
            return Out(text, 15) if num >= 0 else Out(text, 11)
        if k == "decimal" and isinstance(v, Decimal):
            return Out(str(v), 15 if v >= 0 else 11)
        return Out(str(v), 15 if not (isinstance(v, int) and v < 0) else 11)

    def e_Interp(self, n: C.Interp) -> Out:
        parts = []
        for p in n.parts:
            parts.append(escape_text(p) if isinstance(p, str) else "{" + self.ex(p) + "}")
        return Out('"' + "".join(parts) + '"', 15)

    def e_SymLit(self, n: C.SymLit) -> Out:
        return Out(f"the symbol {n.name}" if self.w else f"'{self.nm(n.name)}", 15)

    def e_Name(self, n: C.Name) -> Out:
        if n.ref.kind == "patvar":
            return Out("?" + self.nm(n.name), 15)
        return Out(self.nm(n.name), 15)

    def e_Get(self, n: C.Get) -> Out:
        t = n.target
        if (
            self.w
            and isinstance(t, C.Name)
            and t.name == "it"
            and self.it_depth
            and not n.optional
            and not self.is_local(n.field)
            and n.field not in self.defs
            and n.field not in BUILTIN_NAMES
            and n.field not in RESERVED_SET
            and n.field not in CONTEXTUAL_SET
        ):
            return Out(n.field, 15)
        if self.w:
            links, x = 0, t
            while isinstance(x, C.Get):
                links, x = links + 1, x.target
            base = self.out(t)
            num = isinstance(t, C.Lit) and t.kind in ("integer", "decimal", "approx", "quantity")
            tail_ok = base.text[-1:].isalnum() or base.text[-1:] in ")]"
            if links < 2 and base.prec >= 14 and not base.open and not num and tail_ok:
                text = f"{base.text}'s {n.field}"
            else:
                text = f"the {n.field} of {self.ex(t, 14)}" if not n.optional else f"({base.text})'s {n.field}"
            return Out(text + (", if any" if n.optional else ""), 14, n.optional or text.startswith("the "))
        return Out(f"{self.post(t)}{'?.' if n.optional else '.'}{self.nm(n.field)}", 14)

    def e_Index(self, n: C.Index) -> Out:
        if self.w:
            i = self.closed(n.index, 11)
            tgt = self.ex(n.target, 14)
            tgt = f"({tgt})" if n.optional and self.out(n.target).open or tgt.endswith(", if any") else tgt
            return Out(f"item {i} of {tgt}" + (", if any" if n.optional else ""), 15, True)
        return Out(f"{self.post(n.target)}{'?[' if n.optional else '['}{self.ex(n.index)}]", 14)

    def e_ListLit(self, n: C.ListLit) -> Out:
        return Out("[" + ", ".join(self.ex(x) for x in n.items) + "]", 15)

    def e_SetLit(self, n: C.SetLit) -> Out:
        return Out("{" + ", ".join(self.ex(x) for x in n.items) + "}", 15)

    def e_MapLit(self, n: C.MapLit) -> Out:
        return Out("{" + ", ".join(f"{self.ex(k)}: {self.ex(v)}" for k, v in n.pairs) + "}", 15)

    def e_RecordLit(self, n: C.RecordLit) -> Out:
        if n.base is not None:
            if self.w and isinstance(n.base, C.Name) and n.fields:
                return Out(f"{self.nm(n.base.name)} {self.named(n.fields)}", 14, True)
            inner = ", ".join(f"{self.nm(k)}={self.ex(v)}" for k, v in n.fields)
            return Out(f"{self.closed(n.base, 14)}.with({inner})", 14)
        tname = n.type.ref if isinstance(n.type, C.TName) else "?"
        if not n.fields:
            return Out(self.nm(tname), 15)
        if self.w:
            return Out(f"{tname} {self.named(n.fields)}", 14, True)
        inner = ", ".join(f"{self.nm(k)}={self.ex(v)}" for k, v in n.fields)
        return Out(f"{self.nm(tname)}({inner})", 14)

    def named(self, pairs: tuple[tuple[str, Any], ...]) -> str:
        items = [
            f"{self.nm(k)} {self.closed(v, 11) if i < len(pairs) - 1 else self.ex(v, 11)}"
            for i, (k, v) in enumerate(pairs)
        ]
        return "with " + " and ".join(items)

    def e_TypeTest(self, n: C.TypeTest) -> Out:
        return Out(f"{self.ex(n.value, 7)} is {self.ty(n.type, slot='is')}", 6, self.w)

    def e_Try(self, n: C.Try) -> Out:
        if self.w:
            return Out(f"try {self.ex(n.expr, 11)}", 11, self.out(n.expr).open)
        return Out(f"{self.post(n.expr)}?", 14)

    def e_Quote(self, n: C.Quote) -> Out:
        self.quote += 1
        try:
            body = self.ex(n.expr)
        finally:
            self.quote -= 1
        return Out(f"quote ({body})" if self.w else f"`({body})", 15)

    def e_Unquote(self, n: C.Unquote) -> Out:
        self.quote -= 1
        try:
            return Out("~" + self.closed(n.expr, 14), 15)
        finally:
            self.quote += 1

    def e_TypeExpr(self, n: C.TypeExpr) -> Out:
        t = n.type
        if not self.w and (isinstance(t, C.TApply) or (isinstance(t, C.TName) and t.ref in TYPE_SYM)):
            return Out(self.ty(t), 15)
        if not w_ok(t):
            return Out(self.ty_s(t), 15)
        return Out(f"the type {self.ty_w(t)}", 15, True)

    def e_Lambda(self, n: C.Lambda) -> Out:
        names = [p.name for p in n.params]
        self.locals.append(set(names))
        try:
            body = self.ex(n.body, 2, cond=True)
        finally:
            self.locals.pop()
        if self.w and names:
            return Out("given " + " and ".join(names) + ", " + body, 15, True)
        if len(names) == 1:
            return Out(f"{self.nm(names[0])} => {body}", 15, True)
        return Out("(" + ", ".join(self.nm(x) for x in names) + f") => {body}", 15, True)

    def clause_body(self, lam: Any, cond: bool) -> str:
        """Body of an implicit-`it` clause (R2, R10)."""
        if not isinstance(lam, C.Lambda) or [p.name for p in lam.params] != ["it"]:
            return "(" + self.ex(lam) + ")"
        self.locals.append({"it"})
        self.it_depth.append(len(self.locals))
        try:
            return self.ex(lam.body, 2, cond=True) if cond else self.ex(lam.body, 8)
        finally:
            self.it_depth.pop()
            self.locals.pop()

    # ---- calls and operators -----------------------------------------------------------
    def e_Call(self, n: C.Call, cond: bool = False) -> Out:
        fn = n.fn
        name = fn.name if isinstance(fn, C.Name) and fn.ref.kind in ("builtin", "def") else None
        a = n.args
        if name is not None and fn.ref.kind == "builtin":
            res = self.operator(name, n, a, cond)
            if res is not None:
                return res
        return self.call(n, name)

    def bin(self, a: Any, op: str, b: Any, prec: int, right: bool = False) -> Out:
        lp, rp = (prec + 1, prec) if right else (prec, prec + 1)
        left = self.closed(a, lp) if self.w else self.ex(a, lp)
        ro = self.out(b)
        rt = f"({ro.text})" if ro.prec < rp else ro.text
        return Out(f"{left} {op} {rt}", prec, ro.open and ro.prec >= rp)

    def operator(self, name: str, n: C.Call, a: tuple[Any, ...], cond: bool) -> Out | None:
        w = self.w
        slots = dict(n.slots)
        if name in SYM_OF and name != "join" and len(a) == 2 and not n.slots:
            prec = 12 if name == "power" else (9 if name in ("add", "subtract") else 10)
            if w and name == "floor-divide":
                return Out(f"({self.closed(a[0], 10)} divided by {self.closed(a[1], 11)}, rounded down)", 15)
            return self.bin(a[0], WORDS_OF[name] if w else SYM_OF[name], a[1], prec, name == "power")
        if name == "negate" and len(a) == 1 and not n.slots:
            inner = self.out(a[0])
            if w:
                return Out(f"negative {self.ex(a[0], 11)}", 11, inner.open)
            txt = self.ex(a[0], 11)
            return Out(f"-({txt})" if txt[:1] in "'-" else f"-{txt}", 11)
        if name in CMP_FNS and len(a) == 2 and not n.slots:
            op = CMP_WORDS[name] if w else CMP_SYM_OUT[name]
            return Out(f"{self.ex(a[0], 7, cond)} {op} {self.ex(a[1], 7, cond)}", 6, self.out(a[1]).open)
        if name == "contains" and len(a) == 2 and not n.slots:
            op = "is in" if w else "in"
            return Out(f"{self.ex(a[1], 7, cond)} {op} {self.ex(a[0], 7, cond)}", 6, self.out(a[0]).open)
        if name == "not" and len(a) == 1 and not n.slots:
            return self.negation(a[0], cond)
        if name in ("and", "or") and len(a) == 2 and is_thunk(a[1]) and not n.slots:
            prec = 4 if name == "and" else 3
            other = "or" if name == "and" else "and"

            def side(x: Any, right: bool) -> str:
                o = self.out(x, cond)
                mixed = isinstance(x, C.Call) and isinstance(x.fn, C.Name) and x.fn.name == other
                low = o.prec <= prec if right else (o.prec < prec or o.open)
                return f"({o.text})" if mixed or low or (cond and o.prec == 7) else o.text

            op = name if w else ("&&" if name == "and" else "||")
            return Out(f"{side(a[0], False)} {op} {side(a[1].body, True)}", prec, self.out(a[1].body).open)
        if name == "default" and len(a) == 2 and is_thunk(a[1]) and not n.slots:
            left = self.ex(a[0], 3, cond)
            right = self.ex(a[1].body, 2, cond)
            return Out(f"{left} {'or else' if w else '??'} {right}", 2, self.out(a[1].body).open)
        if name == "between" and len(a) == 3 and set(slots) <= {"low-inclusive", "high-inclusive"}:
            lo_inc = slots.get("low-inclusive", C.Lit("truth", True)) == C.Lit("truth", True)
            hi_inc = slots.get("high-inclusive", C.Lit("truth", True)) == C.Lit("truth", True)
            if all(isinstance(v, C.Lit) and v.kind == "truth" for v in slots.values()):
                x, lo, hi = (self.ex(v, 8 if not w else 7, cond) for v in a)
                if w:
                    mod = (
                        ""
                        if lo_inc and hi_inc
                        else (
                            ", exclusive"
                            if not lo_inc and not hi_inc
                            else (", exclusive above" if lo_inc else ", exclusive below")
                        )
                    )
                    return Out(f"{x} is between {lo} and {hi}{mod}", 6, True)
                return Out(f"{lo} {'<=' if lo_inc else '<'} {x} {'<=' if hi_inc else '<'} {hi}", 6)
        if name == "match" and len(a) == 2 and isinstance(a[1], C.Quote) and not n.slots:
            self.quote += 1
            try:
                pat = self.ex(a[1].expr, 7)
            finally:
                self.quote -= 1
            return Out(f"{self.ex(a[0], 7, cond)} {'matches' if w else '~='} {pat}", 6)
        if name in CLAUSES and not cond:
            res = self.clause(name, n, a)
            if res is not None:
                return res
        if name == "range" and len(a) == 2 and set(slots) <= {"exclusive", "step"}:
            excl = slots.get("exclusive") == C.Lit("truth", True)
            if "exclusive" not in slots or excl:
                step = slots.get("step")
                if w:
                    lo, hi = self.closed(a[0], 9), self.closed(a[1], 9) if step is not None else self.ex(a[1], 9)
                    by = f" by {self.ex(step, 9)}" if step is not None else ""
                    return Out(f"from {lo} {'up to' if excl else 'to'} {hi}{by}", 15, True)
                lo, hi = self.ex(a[0], 9), self.ex(a[1], 9)
                lo = f"({lo})" if lo.endswith("?") else lo
                hi = f"({hi})" if hi[:1] in "'." else hi
                by = f" by {self.ex(step, 9)}" if step is not None else ""
                return Out(f"{lo}{'..<' if excl else '..'}{hi}{by}", 8)
        if name == "problem" and len(a) == 1 and isinstance(a[0], C.SymLit):
            if w or not n.slots:
                tail = " " + self.named(n.slots) if n.slots else ""
                return Out(f"problem {a[0].name}{tail}", 15, bool(n.slots))
        if name == "egraph-simplify" and len(a) == 2 and isinstance(a[1], C.Name):
            tail = " " + self.named(n.slots) if n.slots else ""
            return Out(f"simplify {self.closed(a[0], 11)} using {self.nm(a[1].name)}{tail}", 15, True)
        if name == "egraph-equiv" and len(a) == 3 and isinstance(a[2], C.Name) and not n.slots:
            return Out(f"{self.ex(a[0], 7)} is equivalent to {self.closed(a[1], 7)} using {self.nm(a[2].name)}", 6)
        if name == "evaluate" and len(a) == 1 and w:
            tail = " " + self.named(n.slots) if n.slots else ""
            return Out(f"evaluate {self.closed(a[0], 11) if n.slots else self.ex(a[0], 11)}{tail}", 15, True)
        if name == "map-concurrent" and len(a) == 2 and isinstance(a[1], C.Lambda) and len(a[1].params) == 1 and w:
            return self.each_in(a[0], a[1], " at the same time")
        if (
            name == "map"
            and len(a) == 2
            and isinstance(a[1], C.Lambda)
            and len(a[1].params) == 1
            and w
            and a[1].params[0].name != "it"
        ):
            return self.each_in(a[0], a[1], "")
        if name.startswith("is-") and len(a) == 1 and not n.slots and name[3:] not in RESERVED_SET:
            adj = name[3:]
            if w and adj not in (
                "less",
                "greater",
                "at",
                "equal",
                "the",
                "between",
                "equivalent",
                "nothing",
                "in",
                "not",
            ):
                return Out(f"{self.ex(a[0], 7, cond)} is {adj}", 6)
        return None

    def each_in(self, src: Any, lam: C.Lambda, extra: str) -> Out:
        x = lam.params[0].name
        self.locals.append({x})
        try:
            body = self.ex(lam.body, 2, cond=True)
        finally:
            self.locals.pop()
        return Out(f"each {x} in {self.ex(src, 8)}{extra}, {body}", 15, True)

    def negation(self, x: Any, cond: bool) -> Out:
        w = self.w
        if w and isinstance(x, C.Call) and isinstance(x.fn, C.Name) and len(x.args) == 2 and not x.slots:
            if x.fn.name == "equal":
                return Out(f"{self.ex(x.args[0], 7, cond)} is not equal to {self.ex(x.args[1], 7, cond)}", 6)
            if x.fn.name == "contains":
                return Out(f"{self.ex(x.args[1], 7, cond)} is not in {self.ex(x.args[0], 7, cond)}", 6)
        if (
            not w
            and isinstance(x, C.Call)
            and isinstance(x.fn, C.Name)
            and x.fn.name == "equal"
            and len(x.args) == 2
            and not x.slots
        ):
            return Out(f"{self.ex(x.args[0], 7, cond)} != {self.ex(x.args[1], 7, cond)}", 6)
        if w and isinstance(x, C.TypeTest):
            return Out(f"{self.ex(x.value, 7, cond)} is not {self.ty(x.type, slot='is')}", 6, True)
        if (
            w
            and isinstance(x, C.Call)
            and isinstance(x.fn, C.Name)
            and x.fn.name.startswith("is-")
            and len(x.args) == 1
        ):
            o = self.out(x)
            if o.prec == 6 and " is " in o.text:
                return Out(f"{self.ex(x.args[0], 7, cond)} is not {x.fn.name[3:]}", 6)
        inner = self.ex(x, 5, cond)
        if w:
            return Out(f"not {inner}", 5)
        o = self.out(x)
        return Out(f"!{o.text}" if o.prec >= 14 and o.text[:1] not in "'!-" else f"!({o.text})", 5)

    def clause(self, name: str, n: C.Call, a: tuple[Any, ...]) -> Out | None:
        w = self.w
        slots = dict(n.slots)
        if not w:
            return None
        if name in ("join", "join-all") and len(a) == 2 and not n.slots:
            word = "joined with" if name == "join" else "joined by"
            return Out(f"{self.target(a[0])} {word} {self.ex(a[1], 8)}", 7, self.out(a[1]).open)
        if name == "sort" and len(a) == 1 and not n.slots:
            return Out(f"{self.target(a[0])} sorted", 7)
        is_it = len(a) == 2 and isinstance(a[1], C.Lambda) and [p.name for p in a[1].params] == ["it"]
        if not is_it:
            return None
        if name in ("filter", "map") and not n.slots:
            word = "where" if name == "filter" else "each"
            return Out(f"{self.target(a[0])} {word} {self.clause_body(a[1], True)}", 7, True)
        if name == "sort-by" and set(slots) <= {"descending"}:
            desc = slots.get("descending")
            if desc is None or desc == C.Lit("truth", True):
                tail = ", descending" if desc is not None else ""
                return Out(f"{self.target(a[0])} sorted by {self.clause_body(a[1], False)}{tail}", 7, bool(tail))
        if name == "group-by" and not n.slots:
            return Out(f"{self.target(a[0])} grouped by {self.clause_body(a[1], False)}", 7)
        return None

    def target(self, x: Any) -> str:
        o = self.out(x)
        return f"({o.text})" if o.prec < 7 or o.open else o.text

    def arg(self, x: Any) -> str:
        """A positional argument in paren form; `(a = b)` is bracketed so it is not a keyword."""
        t = self.ex(x)
        return f"({t})" if re.match(r"[^\W\d][\w-]* = ", t) else t

    def call(self, n: C.Call, name: str | None) -> Out:
        fn = n.fn
        sig = self.sigs.get(name or "", None)
        if (
            self.w
            and not self.quote
            and name is not None
            and len(n.args) <= 1
            and (n.args or n.slots)
            and not self.is_local(name)
            and (name in BUILTIN_NAMES or self.defs.get(name) == "func" or "." in name)
        ):
            parts = [self.nm(name)]
            items: list[tuple[str, Any]] = []
            if n.args:
                lead = "of " if sig and sig[0][0] == "of" else ""
                items.append((lead, n.args[0]))
            named = []
            for k, v in n.slots:
                if k in SLOT_WORDS:
                    items.append((k + " ", v))
                else:
                    named.append((k, v))
            if all(k == "" or k in SLOT_WORDS for k, _ in n.slots) or True:
                for i, (lead, v) in enumerate(items):
                    last = i == len(items) - 1 and not named
                    o = self.out(v)
                    txt = o.text
                    starts_slot = txt.split(" ", 1)[0] in SLOT_WORDS
                    if (
                        o.prec < 11
                        or o.prec == 7
                        or (o.open and not last)
                        or starts_slot
                        or (lead == "" and txt[:1] == "-")
                    ):
                        txt = f"({txt})"
                    parts.append(lead + txt)
                if named:
                    parts.append(self.named(tuple(named)))
                return Out(" ".join(parts), 14, True)
        callee = self.closed(fn, 14) if not isinstance(fn, C.Name) else self.nm(fn.name)
        args = [self.arg(x) for x in n.args] + [f"{self.nm(k)}={self.ex(v)}" for k, v in n.slots]
        return Out(f"{callee}({', '.join(args)})", 14)

    # ---- types -------------------------------------------------------------------------
    def ty(self, t: Any, slot: str = "") -> str:
        return self.ty_w(t) if self.w and w_ok(t) else self.ty_s(t)

    def ty_w(self, t: Any, art: bool = True) -> str:
        def a(word: str) -> str:
            return f"{article(word)} {word}" if art else word

        if isinstance(t, C.TName):
            return t.ref if t.ref in MASS else a(t.ref)
        if isinstance(t, C.TVar):
            return t.name
        if isinstance(t, C.TAnything):
            return "anything"
        if isinstance(t, C.TOptional):
            return f"{self.member(t.type, art)} or nothing"
        if isinstance(t, C.TUnion):
            return " or ".join(self.member(x, art) for x in t.types)
        if isinstance(t, C.TApply):
            if t.head == "map":
                return a(f"map from {self.pl(t.args[0])} to {self.pl(t.args[1])}")
            return a(f"{t.head} of {self.pl(t.args[0])}")
        if isinstance(t, C.TFunc):
            ps = " and ".join(self.ty_w(p) for p in t.params)
            eff = f", needs {self.effects(t.effects)}" if t.effects else ""
            return a(f"function from {ps} to {self.ty_w(t.result)}{eff}")
        return "anything"

    def member(self, t: Any, art: bool) -> str:
        """A union member; a type variable takes an article there (`a T or nothing`)."""
        return f"{article(t.name)} {t.name}" if isinstance(t, C.TVar) and art else self.ty_w(t, art)

    def pl(self, t: Any) -> str:
        if isinstance(t, C.TName):
            if t.ref in MASS:
                return t.ref
            if t.ref[:1].isupper():
                return self.plurals.get(t.ref, t.ref)
            return plural_of(t.ref)
        if isinstance(t, C.TAnything):
            return "anything"
        if isinstance(t, C.TApply) and t.head in ("list", "set", "channel"):
            return f"{t.head}s of {self.pl(t.args[0])}"
        if isinstance(t, C.TApply) and t.head == "map":
            return f"maps from {self.pl(t.args[0])} to {self.pl(t.args[1])}"
        if isinstance(t, C.TVar):
            return t.name
        return self.ty_w(t, art=False)

    def ty_s(self, t: Any) -> str:
        if isinstance(t, C.TName):
            return TYPE_SYM.get(t.ref, t.ref)
        if isinstance(t, C.TVar):
            return t.name
        if isinstance(t, C.TAnything):
            return "Anything"
        if isinstance(t, C.TOptional):
            inner = self.ty_s(t.type)
            return f"{inner}?" if not isinstance(t.type, (C.TUnion, C.TFunc)) else f"{inner} | Nothing"
        if isinstance(t, C.TUnion):
            return " | ".join(self.ty_s(x) for x in t.types)
        if isinstance(t, C.TApply):
            return f"{HEAD_SYM[t.head]}[{', '.join(self.ty_s(x) for x in t.args)}]"
        if isinstance(t, C.TFunc):
            eff = f" needs {self.effects(t.effects)}" if t.effects else ""
            return f"({', '.join(self.ty_s(p) for p in t.params)}) -> {self.ty_s(t.result)}{eff}"
        return "Anything"

    def effects(self, row: tuple[C.EffItem, ...]) -> str:
        items = []
        for e in row:
            s = e.effect
            for nw in e.narrowing:
                if nw.kind == "limited-to":
                    s += f" limited to {self.ex(nw.arg, 11)}"
                else:
                    s += ", read only"
            items.append(s)
        return (" and " if self.w else ", ").join(items)

    # ---- patterns ----------------------------------------------------------------------
    def pat(self, p: Any, mode: str) -> str:
        w = self.w
        if isinstance(p, C.PBind):
            base = self.nm(p.name) if mode == "bind" else "?" + self.nm(p.name)
            if p.type is not None:
                base = (
                    f"{'?' + self.nm(p.name)} ({self.ty_w(p.type)})"
                    if w
                    else f"{'?' + self.nm(p.name)}: {self.ty_s(p.type)}"
                )
            return base
        if isinstance(p, C.PWild):
            return "anything" if w else "_"
        if isinstance(p, C.PLit):
            return self.ex(p.lit)
        if isinstance(p, C.PRange):
            lo, hi = self.ex(p.lo.lit), self.ex(p.hi.lit)
            if w:
                return f"from {lo} {'to' if p.inclusive else 'up to'} {hi}"
            return f"{lo}{'..' if p.inclusive else '..<'}{hi}"
        if isinstance(p, C.PAlt):
            return " or ".join(self.pat(x, mode) for x in p.alts)
        if isinstance(p, C.PList):
            items = [self.pat(x, mode) for x in p.prefix]
            if p.rest is not None:
                items.append("..." + self.pat(p.rest, mode))
            return "[" + ", ".join(items) + "]"
        if isinstance(p, C.PQuote):
            self.quote += 1
            try:
                body = self.ex(p.expr)
            finally:
                self.quote -= 1
            return f"quote ({body})" if w else f"`({body})"
        if isinstance(p, (C.PRecord, C.PCase)):
            head = p.type.ref if isinstance(p, C.PRecord) else p.case
            head = head if w else self.nm(head)
            if not p.fields and not p.open:
                return head
            if w:
                items = [
                    k if isinstance(v, C.PBind) and v.name == k and v.type is None else f"{k} {self.pat(v, 'match')}"
                    for k, v in p.fields
                ]
                tail = ", and more" if p.open else ""
                return f"{head} with " + " and ".join(items) + tail
            items = [f"{self.nm(k)}={self.pat(v, 'match')}" for k, v in p.fields] + (["..."] if p.open else [])
            return f"{head}(" + ", ".join(items) + ")"
        return "_"

    # ---- statements --------------------------------------------------------------------
    def block(self, b: C.Block, ind: int, binders: set[str] | None = None) -> list[str]:
        self.locals.append(set(binders or ()))
        lines: list[str] = []
        notes = {i: v for i, k, v in getattr(b, "trivia", ()) if k == "note"}
        try:
            for i, st in enumerate(b.stmts):
                if i in notes:
                    lines += self.note(notes[i], ind)
                lines += self.lead_comments(st, ind)
                lines += self.stmt(st, ind)
        finally:
            self.locals.pop()
        return lines

    def lead_comments(self, n: Any, ind: int) -> list[str]:
        line = getattr(n, "line", 0) or 0
        out = []
        while self.comments and line and self.comments[0][0] < line:
            c = self.comments.pop(0)
            out.append(" " * ind + c[2])
        return out

    def trail(self, n: Any) -> str:
        line = getattr(n, "line", 0) or 0
        if self.comments and line and self.comments[0][0] == line and not self.comments[0][3]:
            return "  " + str(self.comments.pop(0)[2])
        return ""

    def note(self, lines: Any, ind: int) -> list[str]:
        texts = [t for _, t in lines]
        first = " " * ind + "note: " + (texts[0] if texts else "")
        return [first.rstrip()] + [" " * (ind + 4) + t for t in texts[1:]]

    def bind_locals(self, names: Any) -> None:
        self.locals[-1].update(names)

    def stmt(self, s: Any, ind: int) -> list[str]:
        pad = " " * ind
        w = self.w
        tr = self.trail(s)
        if isinstance(s, C.Bind):
            target = self.pat(s.target, "bind")
            ty = f": {self.ty(s.type)}" if s.type is not None else ""
            if isinstance(s.value, C.Concurrent):
                head = f"{pad}{'var' if s.mutable and not w else 'let'} {target}{ty} {'be' if w else '='} "
                if w and s.mutable:
                    head = f"{pad}let {target}{ty} be "
                self.bind_locals(pattern_names(s.target))
                return self.concurrent(s.value, ind, head)
            val = self.ex(s.value)
            self.bind_locals(pattern_names(s.target))
            if w:
                return [f"{pad}let {target}{ty} be {val}{', changeable' if s.mutable else ''}{tr}"]
            return [f"{pad}{'var' if s.mutable else 'let'} {target}{ty} = {val}{tr}"]
        if isinstance(s, C.Rebind):
            name = self.nm(s.name.name)
            v = s.value
            if (
                isinstance(v, C.Call)
                and isinstance(v.fn, C.Name)
                and v.fn.name == "added"
                and len(v.args) == 2
                and not v.slots
                and v.args[0] == s.name
            ):
                if w:
                    item = self.out(v.args[1])
                    txt = item.text if item.prec >= 11 and item.prec != 7 and not item.open else f"({item.text})"
                    return [f"{pad}add {txt} to {name}{tr}"]
                return [f"{pad}{name} += {self.ex(v.args[1])}{tr}"]
            if isinstance(v, C.Concurrent):
                return self.concurrent(v, ind, f"{pad}{'set ' + name + ' to ' if w else name + ' := '}")
            return [f"{pad}set {name} to {self.ex(v)}{tr}" if w else f"{pad}{name} := {self.ex(v)}{tr}"]
        if isinstance(s, C.SetField):
            if w:
                return [f"{pad}change the {s.field} of {self.closed(s.target, 14)} to {self.ex(s.value)}{tr}"]
            return [f"{pad}{self.closed(s.target, 14)}.{self.nm(s.field)} := {self.ex(s.value)}{tr}"]
        if isinstance(s, C.ExprStmt):
            if isinstance(s.expr, C.Concurrent):
                return self.concurrent(s.expr, ind, pad)
            return [f"{pad}{self.ex(s.expr)}{tr}"]
        if isinstance(s, C.Return):
            kw = "give back" if w else "return"
            if s.value is None:
                return [f"{pad}{kw}{tr}"]
            if isinstance(s.value, C.Concurrent):
                return self.concurrent(s.value, ind, f"{pad}{kw} ")
            return [f"{pad}{kw} {self.ex(s.value)}{tr}"]
        if isinstance(s, C.Stop):
            return [f"{pad}{'stop' if w else 'break'}{tr}"]
        if isinstance(s, C.Skip):
            return [f"{pad}{'skip' if w else 'continue'}{tr}"]
        if isinstance(s, C.If):
            out: list[str] = []
            for i, br in enumerate(s.branches):
                kw = "if" if i == 0 else ("otherwise if" if w else "elif")
                out.append(f"{pad}{kw} {self.ex(br.cond)}:{tr if i == 0 else ''}")
                out += self.block(br.body, ind + 4)
            if s.else_ is not None:
                out.append(f"{pad}{'otherwise' if w else 'else'}:")
                out += self.block(s.else_, ind + 4)
            return out
        if isinstance(s, C.Match):
            out = [f"{pad}match {self.ex(s.subject)}:{tr}"]
            for mc in s.cases:
                names = pattern_names(mc.pattern)
                self.locals.append(set(names))
                try:
                    guard = ""
                    if mc.guard is not None:
                        guard = f", if {self.ex(mc.guard)}" if w else f" if {self.ex(mc.guard)}"
                    out.append(f"{pad}    {'when' if w else 'case'} {self.pat(mc.pattern, 'match')}{guard}:")
                    out += self.block(mc.body, ind + 8)
                finally:
                    self.locals.pop()
            if s.else_ is not None:
                out.append(f"{pad}    {'otherwise' if w else 'else'}:")
                out += self.block(s.else_, ind + 8)
            return out
        if isinstance(s, C.For):
            return self.for_stmt(s, pad, ind, tr)
        if isinstance(s, C.While):
            return [f"{pad}while {self.ex(s.cond)}:{tr}"] + self.block(s.body, ind + 4)
        if isinstance(s, C.WithCap):
            narrow = ""
            for nw in s.narrowing:
                narrow += f" limited to {self.ex(nw.arg, 11)}" if nw.kind == "limited-to" else ", read only"
            cap = s.cap.name if isinstance(s.cap, C.Name) else "?"
            return [f"{pad}with {cap}{narrow}:{tr}"] + self.block(s.body, ind + 4)
        if isinstance(s, C.Within):
            return [f"{pad}within {self.closed(s.limit, 11)}:{tr}"] + self.block(s.body, ind + 4)
        if isinstance(s, C.Concurrent):
            return self.concurrent(s, ind, pad)
        if isinstance(s, C.Check):
            return self.check(s, ind)
        return [f"{pad}nothing"]

    def for_stmt(self, s: C.For, pad: str, ind: int, tr: str) -> list[str]:
        w = self.w
        src = s.source
        names = pattern_names(s.binder)
        is_call = isinstance(src, C.Call) and isinstance(src.fn, C.Name)
        if (
            isinstance(s.binder, C.PWild)
            and is_call
            and src.fn.name == "range"
            and len(src.args) == 2
            and not src.slots
            and src.args[0] == C.Lit("integer", 1)
        ):
            head = f"repeat {self.ex(src.args[1], 2)} times:" if w else f"for _ in 1..{self.ex(src.args[1], 9)}:"
            return [pad + head + tr] + self.block(s.body, ind + 4)
        target = self.pat(s.binder, "bind")
        if w and is_call and src.fn.name == "received" and len(src.args) == 1 and not src.slots:
            head = f"for each {target} received from {self.ex(src.args[0])}:"
        else:
            head = f"for each {target} in {self.ex(src)}:" if w else f"for {target} in {self.ex(src)}:"
        return [pad + head + tr] + self.block(s.body, ind + 4, set(names))

    def concurrent(self, c: C.Concurrent, ind: int, head: str) -> list[str]:
        pad = " " * ind
        if c.mode == "together":
            out = [f"{pad}together:"]
            for ch in c.children:
                body = ch.body if isinstance(ch.body, C.Block) else C.Block((C.ExprStmt(ch.body),))
                out += self.block(body, ind + 4)
            return out
        kw = f"{c.mode} of:" if self.w else f"{c.mode}_of:"
        out = [head + kw]
        for ch in c.children:
            label = f"{self.nm(ch.label)}: " if ch.label else ""
            out.append(f"{pad}    {label}{self.ex(ch.body)}")
        return out

    def check(self, s: C.Check, ind: int) -> list[str]:
        pad = " " * ind
        w = self.w
        if s.body is not None:
            return [f'{pad}check "{escape_text(s.label or "")}":'] + self.block(s.body, ind + 4)
        subj = self.closed(s.subject, 7)
        lead = "check that " if w else "check "
        if s.relation == "equals":
            return [f"{pad}{lead}{subj} {'equals' if w else '='} {self.closed(s.expected, 7)}"]
        if s.relation == "fails-with" and isinstance(s.expected, C.SymLit):
            return [f"{pad}{lead}{self.ex(s.subject, 2)} {'fails with' if w else 'fails'} {s.expected.name}"]
        if s.relation == "matches" and isinstance(s.expected, C.Quote):
            self.quote += 1
            try:
                pat = self.ex(s.expected.expr, 7)
            finally:
                self.quote -= 1
            return [f"{pad}{lead}{subj} {'matches' if w else '~='} {pat}"]
        if s.relation == "is" and isinstance(s.expected, C.TypeExpr):
            return [f"{pad}{lead}{subj} is {self.ty(s.expected.type, slot='is')}"]
        return [f"{pad}{lead}{self.ex(s.subject)}"]

    # ---- declarations ------------------------------------------------------------------
    def param(self, p: C.Param) -> str:
        lead = f"{p.slot} " if p.slot else ""
        if self.w:
            inner = []
            if p.type is not None:
                inner.append(self.ty(p.type))
            if p.default is not None:
                inner.append(f"default {self.ex(p.default)}")
            if inner and p.type is None:
                inner.insert(0, "anything")
            return f"{lead}{p.name}" + (f" ({', '.join(inner)})" if inner else "")
        ty = f": {self.ty_s(p.type)}" if p.type is not None else ""
        df = f" = {self.ex(p.default)}" if p.default is not None else ""
        return f"{lead}{self.nm(p.name)}{ty}{df}"

    def func(self, f: C.Func) -> list[str]:
        w = self.w
        self.locals = [{p.name for p in f.params}]
        if w:
            head = "to " + " ".join([f.name] + [self.param(p) for p in f.params])
            if f.result is not None:
                head += f" giving {self.ty(f.result)}"
            if f.effects:
                head += f", needs {self.effects(f.effects)}"
            if f.fails:
                head += ", may fail with " + " and ".join(f.fails)
            if f.generics:
                head += ", for any " + " and ".join(g.name for g in f.generics)
        else:
            gen = f"[{', '.join(g.name for g in f.generics)}]" if f.generics else ""
            head = f"def {self.nm(f.name)}{gen}({', '.join(self.param(p) for p in f.params)})"
            if f.result is not None:
                head += f" -> {self.ty_s(f.result)}"
            if f.effects:
                head += f" needs {self.effects(f.effects)}"
            if f.fails:
                head += " fails " + ", ".join(self.nm(k) for k in f.fails)
        lines = [head + ":" + self.trail(f)] + self.block(f.body, 4)
        self.locals = [set()]
        return lines

    def field_w(self, fd: C.FieldDef) -> str:
        df = f", default {self.ex(fd.default)}" if fd.default is not None else ""
        return f"{article(fd.name)} {fd.name} ({self.ty(fd.type)}{df})"

    def field_s(self, fd: C.FieldDef) -> str:
        df = f" = {self.ex(fd.default)}" if fd.default is not None else ""
        return f"{self.nm(fd.name)}: {self.ty_s(fd.type)}{df}"

    def type_head(self, name: str, plural: str, tparams: tuple[C.TParam, ...]) -> str:
        pl = f" (plural {plural})" if plural != plural_of(name) else ""
        if self.w:
            of = " of " + " and ".join(t.name for t in tparams) if tparams else ""
            return f"{article(name)} {name}{of}{pl}"
        tp = f"[{', '.join(t.name for t in tparams)}]" if tparams else ""
        return f"{name}{tp}{pl}"

    def record(self, r: C.RecordDef) -> list[str]:
        self.locals = [{f.name for f in r.fields}]
        try:
            if self.w:
                line = f"{self.type_head(r.name, r.plural, r.tparams)} has " + " and ".join(
                    self.field_w(fd) for fd in r.fields
                )
                if r.changeable:
                    line += ", changeable"
                for inv in r.invariants:
                    line += f", where {self.ex(inv)}"
                return [line]
            line = f"{'var ' if r.changeable else ''}record {self.type_head(r.name, r.plural, r.tparams)}("
            line += ", ".join(self.field_s(fd) for fd in r.fields) + ")"
            if r.invariants:
                line += f" where {self.ex(r.invariants[0])}"
            return [line]
        finally:
            self.locals = [set()]

    def variant(self, v: C.VariantDef) -> list[str]:
        if self.w:
            out = [f"{self.type_head(v.name, v.plural, v.tparams)} is one of:"]
            for c in v.cases:
                fs = " with " + " and ".join(self.field_w(fd) for fd in c.fields) if c.fields else ""
                out.append(f"    {c.name}{fs}")
            return out
        out = [f"variant {self.type_head(v.name, v.plural, v.tparams)}:"]
        for c in v.cases:
            fs = "(" + ", ".join(self.field_s(fd) for fd in c.fields) + ")" if c.fields else ""
            out.append(f"    {self.nm(c.name)}{fs}")
        return out

    def ruleset(self, r: C.Ruleset) -> list[str]:
        out = [f"ruleset {self.nm(r.name)}:"]
        self.quote += 1
        try:
            for rule in r.rules:
                lhs = rule.lhs.expr if isinstance(rule.lhs, C.PQuote) else rule.lhs
                lt, rt = self.ex(lhs, 2), self.ex(rule.rhs, 2)
                if self.w:
                    g = f" when {self.ex(rule.guard)}" if rule.guard is not None else ""
                    out.append(f"    rewrite {lt} as {rt}{g}")
                else:
                    g = f" if {self.ex(rule.guard)}" if rule.guard is not None else ""
                    out.append(f"    {lt} => {rt}{g}")
        finally:
            self.quote -= 1
        return out

    def decl(self, d: Any) -> list[str]:
        if isinstance(d, C.Func):
            return self.func(d)
        if isinstance(d, C.RecordDef):
            return self.record(d)
        if isinstance(d, C.VariantDef):
            return self.variant(d)
        if isinstance(d, C.Ruleset):
            return self.ruleset(d)
        if isinstance(d, C.Check):
            return self.check(d, 0)
        if isinstance(d, C.Bind):
            return self.stmt(d, 0)
        return [f"# unprintable {type(d).__name__}"]

    def module(self, m: C.Module) -> str:
        out: list[str] = []
        if m.has_header or m.name != "main":
            out.append(f"module {m.name}")
        out.append(f"edition {m.edition}")
        for u in sorted(m.uses, key=lambda u: u.path):
            names = f": {', '.join(u.names)}" if u.names else ""
            alias = f" as {u.alias}" if u.alias else ""
            out.append(f"use {u.path}{names}{alias}")
        if m.needs:
            out.append(f"needs {self.effects(m.needs)}")
        if m.dialects:
            out.append("dialect " + ", ".join(sorted(m.dialects)))
        notes: dict[int, list[Any]] = {}
        for i, kind, v in m.trivia:
            if kind == "note":
                notes.setdefault(i, []).append(v)
        for i, d in enumerate(m.body):
            out += ["", ""]
            for nt in notes.get(i, []):
                out += self.note(nt, 0)
            out += self.lead_comments(d, 0)
            out += self.decl(d)
        for nt in notes.get(len(m.body), []):
            out += ["", ""] + self.note(nt, 0)
        out += [c[2] for c in self.comments]
        return "\n".join(out) + "\n"


def w_ok(t: Any, plural: bool = False) -> bool:
    """Can the words type grammar express `t` (spec 03-grammar.ebnf section 9)?"""
    if isinstance(t, (C.TName, C.TVar, C.TAnything)):
        return True
    if isinstance(t, C.TApply):
        return all(w_ok(a, True) for a in t.args)
    if plural:
        return False
    if isinstance(t, C.TOptional):
        return w_ok(t.type)
    if isinstance(t, C.TUnion):
        return all(w_ok(x) for x in t.types)
    if isinstance(t, C.TFunc):
        return all(w_ok(x, True) or isinstance(x, C.TFunc) and w_ok(x) for x in (*t.params, t.result))
    return False


def is_thunk(x: Any) -> bool:
    return isinstance(x, C.Lambda) and not x.params


def pattern_names(p: Any) -> list[str]:
    return [x.name for x in C.walk(p) if isinstance(x, C.PBind)]


def print_module(m: C.Module, surface: str = "words", comments: list[Any] | None = None) -> str:
    return Printer(surface, m, comments).module(m)


def print_expr(e: Any, surface: str = "symbols") -> str:
    p = Printer(surface)
    p.quote = 1
    return p.ex(e)


def expr_text(e: Any) -> str:
    """An Expression or type in the canonical ASCII symbols surface (used by `display`)."""
    return print_expr(e, "symbols")
