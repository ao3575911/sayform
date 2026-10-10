"""`say explain` (spec/13-tooling.md section 3): English sentences for what the core means.
Every node has a template (L7); anything without a dedicated template is described by its
canonical words form, so explain is total."""

from __future__ import annotations

import string
from typing import Any

from . import core as C
from .keywords import SLOT_WORDS
from .printer import Printer, expr_text

OPS = {"add": "plus", "subtract": "minus", "multiply": "times", "divide": "divided by"}
WHO = {
    "together": "Run these at the same time and wait for all of them",
    "all": "Run these at the same time and collect every result",
    "first": "Run these at the same time; keep the first that succeeds and cancel the rest",
}
WHAT = {
    "all": "the results of these, run at the same time",
    "first": "the first of these to succeed, run at the same time, cancelling the rest",
}


class Explainer:
    def __init__(self, mod: C.Module) -> None:
        self.p = Printer("words", mod)
        self.types = {d.plural: d.name for d in mod.body if isinstance(d, (C.RecordDef, C.VariantDef))}
        self.lines: list[str] = []
        self.notes: list[str] = []

    def np(self, n: Any, depth: int = 0) -> str:
        if depth > 3 and isinstance(n, C.Call):
            self.notes.append(self.np(n))
            return f"({len(self.notes)})"
        d = depth + 1
        if isinstance(n, C.Call) and isinstance(n.fn, C.Name):
            name, a = n.fn.name, n.args
            if n.fn.ref.kind == "builtin" and name in OPS and len(a) == 2:
                return f"{self.np(a[0], d)} {OPS[name]} {self.np(a[1], d)}"
            if n.fn.ref.kind == "builtin" and name == "count" and len(a) == 1:
                return f"the number of items in {self.np(a[0], d)}"
            if n.fn.ref.kind == "builtin" and name == "filter" and len(a) == 2:
                return f"{self.np(a[0], d)} whose {self.p.clause_body(a[1], True)}"
            if n.fn.ref.kind == "builtin" and name == "show" and len(a) == 1:
                return f"show {self.np(a[0], d)}"
            if n.fn.ref.kind == "def":
                args = [self.np(x, d) for x in a] + [f"{k} {self.np(v, d)}" for k, v in n.slots]
                return f"the result of {name}" + (" given " + ", ".join(args) if args else "")
        if isinstance(n, C.Try):
            return f"{self.np(n.expr, d)}, stopping here and passing on any problem"
        if isinstance(n, C.Lambda):
            given = " and ".join(x.name for x in n.params)
            return f"a function that, given {given}, gives {self.np(n.body, d)}"
        if isinstance(n, C.Quote):
            return f"the expression `{expr_text(n.expr)}`"
        if isinstance(n, C.Concurrent):
            return WHAT.get(n.mode, WHO[n.mode].lower())
        return self.p.ex(n)

    def say(self, line: int, level: int, text: str) -> None:
        text = text[:1].upper() + text[1:]
        self.lines.append(f"L{line}: {'  ' * level}{text}{'' if text.endswith(':') else '.'}")
        self.lines += [f"    where ({i}) is {x}." for i, x in enumerate(self.notes, 1)]
        self.notes = []

    def children(self, c: C.Concurrent, level: int) -> None:
        for letter, ch in zip(string.ascii_lowercase, c.children, strict=False):
            body = ch.body.stmts[0] if isinstance(ch.body, C.Block) else ch.body
            tag = f"({letter}) " + (f"{ch.label}: " if ch.label else "")
            if isinstance(ch.body, C.Block):
                self.stmt(body, level, tag)
            else:
                self.say(body.line, level, tag + self.np(body))

    def block(self, b: Any, level: int) -> None:
        for st in b.stmts if isinstance(b, C.Block) else (b,):
            self.stmt(st, level)

    def stmt(self, s: Any, level: int, tag: str = "") -> None:  # noqa: C901 - one template per node
        val = getattr(s, "value", None) if isinstance(s, (C.Bind, C.Return)) else None
        if isinstance(s, C.ExprStmt):
            val = s.expr
        conc = val if isinstance(val, C.Concurrent) else None
        if isinstance(s, C.Bind):
            name = s.target.name if isinstance(s.target, C.PBind) else self.p.pat(s.target, "bind")
            how = ":" if conc else (", which can change later" if s.mutable else ", which never changes")
            self.say(s.line, level, f"{tag}let `{name}` be {self.np(s.value)}{how}")
        elif isinstance(s, C.Rebind):
            self.say(s.line, level, f"{tag}change `{s.name.name}` to {self.np(s.value)}")
        elif isinstance(s, C.SetField):
            self.say(s.line, level, f"{tag}change {self.np(s.target)}'s {s.field} to {self.np(s.value)}")
        elif isinstance(s, C.If):
            for i, br in enumerate(s.branches):
                line = s.line if i == 0 else max(s.line, first_line(br.body) - 1)
                self.say(line, level, f"{tag if i == 0 else ''}{'otherwise, if' if i else 'if'} {self.np(br.cond)}:")
                self.block(br.body, level + 1)
            if s.else_ is not None:
                self.say(first_line(s.else_) - 1, level, "otherwise:")
                self.block(s.else_, level + 1)
        elif isinstance(s, C.Match):
            self.say(s.line, level, f"{tag}look at {self.np(s.subject)}:")
            for case in s.cases:
                guard = f", if {self.np(case.guard)}" if case.guard is not None else ""
                self.say(
                    first_line(case.body) - 1, level + 1, f"when it is {self.p.pat(case.pattern, 'match')}{guard}:"
                )
                self.block(case.body, level + 2)
            if s.else_ is not None:
                self.say(first_line(s.else_) - 1, level + 1, "otherwise:")
                self.block(s.else_, level + 2)
        elif isinstance(s, C.For):
            src = s.source
            if isinstance(s.binder, C.PWild) and isinstance(src, C.Call) and getattr(src.fn, "name", "") == "range":
                head = f"repeat {self.np(src.args[-1])} times:"
            else:
                head = f"for each `{self.p.pat(s.binder, 'bind')}` in {self.np(src)}:"
            self.say(s.line, level, tag + head)
            self.block(s.body, level + 1)
        elif isinstance(s, C.While):
            self.say(s.line, level, f"{tag}while {self.np(s.cond)}:")
            self.block(s.body, level + 1)
        elif isinstance(s, (C.Stop, C.Skip)):
            self.say(s.line, level, tag + ("stop the loop" if isinstance(s, C.Stop) else "skip to the next item"))
        elif isinstance(s, C.Return):
            what = "nothing" if s.value is None else self.np(s.value)
            self.say(s.line, level, f"{tag}give back {what}{':' if conc else ''}")
        elif isinstance(s, C.WithCap):
            self.say(s.line, level, f"{tag}using only {self.p.effects((C.EffItem(s.cap, s.narrowing),))}:")
            self.block(s.body, level + 1)
        elif isinstance(s, C.Concurrent):
            self.say(s.line, level, f"{tag}{WHO[s.mode]}:")
            conc = s
        elif isinstance(s, C.Within):
            self.say(s.line, level, f"{tag}within {self.np(s.limit)}, otherwise fail with timed-out:")
            self.block(s.body, level + 1)
        elif isinstance(s, C.Check):
            self.check(s, level)
        elif isinstance(s, C.ExprStmt):
            self.say(s.line, level, tag + self.np(s.expr) + (":" if conc else ""))
        else:
            self.say(getattr(s, "line", 0), level, tag + self.p.ex(s))
        if conc is not None:
            self.children(conc, level + 1)

    def check(self, s: C.Check, level: int) -> None:
        if s.body is not None:
            self.say(s.line, level, f'check "{s.label}":')
            self.block(s.body, level + 1)
            return
        rel = {"equals": " equals ", "is": " is ", "fails-with": " fails with ", "matches": " matches "}
        exp = "" if s.expected is None else rel.get(s.relation, " ") + self.p.ex(s.expected)
        self.say(s.line, level, f"check that {self.np(s.subject)}{exp}")

    def param(self, x: C.Param) -> str:
        """As declared, without the lead word; user types keep their own name (spec 13 E2)."""
        text = self.p.param(C.Param(x.name, x.slot if x.slot in SLOT_WORDS else None, x.type, x.default))
        for plural, name in self.types.items():
            text = text.replace(f"of {plural})", f"of {name})")
        return text

    def decl(self, d: Any) -> None:
        p = self.p
        if isinstance(d, C.Func):
            p.locals = [{x.name for x in d.params}]
            sig = f"Function `{d.name}`: takes {', '.join(self.param(x) for x in d.params) or 'nothing'}; "
            sig += f"gives {p.ty(d.result) if d.result is not None else 'nothing'}; "
            sig += f"may use {p.effects(d.effects) or 'nothing'}"
            self.lines.append(sig + (f"; may fail with {' and '.join(d.fails)}." if d.fails else "."))
            self.block(d.body, 1)
            p.locals = [set()]
        elif isinstance(d, C.RecordDef):
            p.locals = [{f.name for f in d.fields}]
            line = f"Record `{d.name}`: has " + " and ".join(p.field_w(f) for f in d.fields)
            if d.invariants:
                line += f"; every {d.name} must satisfy: " + " and ".join(p.ex(x) for x in d.invariants)
            self.lines.append(line + ".")
            p.locals = [set()]
        elif isinstance(d, C.VariantDef):
            self.lines.append(f"Variant `{d.name}`: is one of " + ", ".join(c.name for c in d.cases) + ".")
        elif isinstance(d, C.Ruleset):
            self.lines.append(f"Ruleset `{d.name}`:")
            for r in d.rules:
                when = f", when {self.np(r.guard)}" if r.guard is not None else ""
                self.say(r.line, 1, f"rewrite {self.np(r.lhs)} as {self.np(r.rhs)}{when}")
        else:
            self.stmt(d, 0)


def first_line(b: Any) -> int:
    stmts = b.stmts if isinstance(b, C.Block) else (b,)
    return int(getattr(stmts[0], "line", 1) if stmts else 1)


def explain(mod: C.Module, line: int | None = None) -> list[str]:
    ex = Explainer(mod)
    ex.lines.append(f"Module {mod.name}, edition {mod.edition}.")
    ex.lines.append(f"It may use: {ex.p.effects(mod.needs) or 'nothing'}.")
    starts = [d.line for d in mod.body] + [10**9]
    for i, d in enumerate(mod.body):
        if line is None or starts[i] <= line < starts[i + 1]:
            ex.decl(d)
    return ex.lines
