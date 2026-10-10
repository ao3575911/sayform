"""Parser for both surfaces (spec/03-grammar.md, spec/03-grammar.ebnf).

A recursive-descent parser over the token stream from `lexer.py`. It applies the
disambiguation rules R1-R20 and lowers directly to the core (spec 04 section 3) using the
tables in `lower.py`; `finish()` then normalises slot and field order. Names are resolved
as they are bound (locals get binding-order indices, spec 04 section 5).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import fields, replace
from typing import Any

from . import core as C
from .diagnostics import SayError, Sink
from .keywords import CONTEXTUAL_SET, EFFECTS, LEADS, RESERVED_SET, SLOT_WORDS
from .lexer import Lexed, Tok, lex, lex_inline
from .lower import (
    BUILTIN_NAMES,
    CMP_SYM,
    HOST_MODULES,
    HOST_SIGS,
    PRELUDE_SIGS,
    SYM_BINOPS,
    WORD_BINOPS,
    is_op,
    op_call,
    thunk,
)

TYPEWORDS = {
    "number",
    "integer",
    "decimal",
    "rational",
    "approx",
    "truth",
    "symbol",
    "expression",
    "problem",
    "type",
    "capability",
}
PLURALS = {
    "numbers": "number",
    "integers": "integer",
    "decimals": "decimal",
    "rationals": "rational",
    "approxes": "approx",
    "truths": "truth",
    "symbols": "symbol",
    "expressions": "expression",
    "problems": "problem",
    "types": "type",
    "lists": "list",
    "sets": "set",
    "maps": "map",
    "functions": "function",
    "channels": "channel",
}
SYM_TYPES = {
    "Number": "number",
    "Integer": "integer",
    "Decimal": "decimal",
    "Rational": "rational",
    "Approx": "approx",
    "Truth": "truth",
    "Symbol": "symbol",
    "Expression": "expression",
    "Problem": "problem",
    "Type": "type",
    "Capability": "capability",
    "Text": "text",
    "Nothing": "nothing",
}
SYM_HEADS = {"List": "list", "Set": "set", "Map": "map", "Channel": "channel"}
OPWORDS = {"plus", "minus", "times", "divided", "mod", "joined", "sorted", "grouped", "matches"}
VALUE_RESERVED = {
    "the",
    "quote",
    "given",
    "yes",
    "no",
    "true",
    "false",
    "nothing",
    "try",
    "evaluate",
    "simplify",
}
V01_DIALECTS = {"money", "units", "ieee", "quick-script"}


def plural_of(name: str) -> str:
    low = name[0].lower() + name[1:]
    return low + ("es" if low.endswith(("s", "x", "z", "ch", "sh")) else "s")


def article_for(word: str) -> str:
    """F-R6 articles with the closed exception table (spec 05 section 2.2)."""
    w = word.lower()
    if w in ("unit", "user", "url", "uuid"):
        return "a"
    if w in ("hour", "sms") or word.startswith(("HTTP", "MCP")):
        return "an"
    return "an" if w[:1] in "aeiou" else "a"


class Scope:
    def __init__(self, kind: str = "block") -> None:
        self.names: dict[str, tuple[int, bool]] = {}
        self.kind = kind


class Parser:
    def __init__(
        self,
        lexed: Lexed,
        file: str = "",
        sink: Sink | None = None,
        known: dict[str, str] | None = None,
        sigs: dict[str, Any] | None = None,
    ) -> None:
        self.t = lexed.tokens
        self.lexed = lexed
        self.p = 0
        self.file = file
        self.sink = sink or Sink()
        self.defs: dict[str, str] = dict(known or {})
        self.fields_known: set[str] = {"left", "right"}
        self.sigs: dict[str, Any] = dict(sigs or {})
        self.scopes: list[Scope] = []
        self.counter = 0
        self.it_stack: list[int] = []
        self.quote = 0
        self.patvars: dict[str, int] | None = None
        self.stop: set[str] = set()
        self.nolambda = False
        self.parens: set[int] = set()
        self.modules: set[str] = set(HOST_MODULES)
        self.in_func = False
        self.loops = 0
        self.blocks: list[tuple[int, int, list[int], Any]] = []
        self.plural_names: dict[str, str] = {}

    # ---- token helpers ---------------------------------------------------------------
    @property
    def cur(self) -> Tok:
        return self.t[self.p]

    def nxt(self, k: int = 1) -> Tok:
        return self.t[min(self.p + k, len(self.t) - 1)]

    def adv(self) -> Tok:
        tok = self.t[self.p]
        if self.p < len(self.t) - 1:
            self.p += 1
        return tok

    def at(self, *words: str) -> bool:
        return self.cur.kind == "NAME" and self.cur.value in words

    def at_op(self, *ops: str) -> bool:
        return self.cur.kind == "OP" and self.cur.value in ops

    def eat(self, *words: str) -> bool:
        if self.at(*words):
            self.adv()
            return True
        return False

    def eat_op(self, *ops: str) -> bool:
        if self.at_op(*ops):
            self.adv()
            return True
        return False

    def describe(self, tok: Tok) -> str:
        if tok.kind in ("NEWLINE", "EOF"):
            return "end of line" if tok.kind == "NEWLINE" else "end of file"
        if tok.kind in ("INDENT", "DEDENT"):
            return "indentation"
        return str(tok.raw or tok.value)

    def fail(
        self,
        expected: str,
        hint: str = "check the line against the grammar",
        tok: Tok | None = None,
    ) -> SayError:
        tok = tok or self.cur
        return SayError(
            "E0130",
            tok.line,
            tok.col,
            token=self.describe(tok),
            expected=expected,
            try_=f"expected {expected}; {hint}",
        )

    def expect(self, word: str) -> Tok:
        if not self.at(word):
            raise self.fail(f"`{word}`")
        return self.adv()

    def expect_op(self, op: str) -> Tok:
        if not self.at_op(op):
            raise self.fail(f"`{op}`")
        return self.adv()

    def end_line(self) -> None:
        if self.cur.kind == "NEWLINE":
            self.adv()
        elif self.cur.kind not in ("EOF", "DEDENT"):
            raise self.fail("the end of the line")

    def word(self, what: str = "a name") -> str:
        tok = self.cur
        if tok.kind == "POSS":
            raise SayError("E0109", tok.line, tok.col, word="'s")
        if tok.kind != "NAME":
            raise self.fail(what)
        if tok.value in RESERVED_SET:
            raise SayError("E0109", tok.line, tok.col, word=tok.value)
        self.adv()
        return str(tok.value)

    def line_text(self, line: int) -> str:
        lines = self.lexed.source.splitlines()
        return lines[line - 1].strip() if 0 < line <= len(lines) else ""

    # ---- scopes ------------------------------------------------------------------------
    @contextmanager
    def scope(self, kind: str = "block") -> Iterator[Scope]:
        s = Scope(kind)
        self.scopes.append(s)
        try:
            yield s
        finally:
            self.scopes.pop()

    def bind(self, name: str, mutable: bool = False, line: int = 0, check: bool = True) -> int:
        if name in CONTEXTUAL_SET and check:
            self.sink.warn("W0114", line, word=name)
        sc = self.scopes[-1]
        if name in sc.names and check:
            raise SayError(
                "E0301",
                line,
                name=name,
                at_line=line,
                what=f"`{name}` is already bound in this block.",
            )
        idx = self.counter
        self.counter += 1
        sc.names[name] = (idx, mutable)
        return idx

    def lookup(self, name: str) -> tuple[int, bool, int] | None:
        for depth in range(len(self.scopes) - 1, -1, -1):
            if name in self.scopes[depth].names:
                i, m = self.scopes[depth].names[name]
                return i, m, depth
        return None

    def ref_for(self, name: str) -> C.Ref:
        loc = self.lookup(name)
        if loc is not None and not self.quote:
            return C.Ref("local", loc[0])
        if self.quote:
            return C.Ref("builtin" if name in BUILTIN_NAMES else "free", name)
        if name in self.defs:
            return C.Ref("def", name)
        if name in BUILTIN_NAMES:
            return C.Ref("builtin", name)
        return C.Ref("free", name)

    def name_node(self, name: str, line: int) -> Any:
        """Resolve a bare name in value position, applying R10 (implicit `it`)."""
        if self.it_stack and not self.quote:
            loc = self.lookup(name)
            it_depth = self.it_stack[-1]
            if loc is None and name not in self.defs and name not in BUILTIN_NAMES:
                return C.Get(self.it_name(line), name, False, line=line)
            if loc is not None and loc[2] < it_depth and name in self.fields_known:
                r1, r2 = f"the local `{name}`", f"the field `{name}` of `it`"
                raise SayError(
                    "E0108",
                    line,
                    readings=[r1, r2],
                    reading1=r1,
                    reading2=r2,
                    symbols1=name,
                    symbols2=f"it.{name}",
                )
        return C.Name(name, self.ref_for(name), line=line)

    def it_name(self, line: int) -> C.Name:
        loc = self.lookup("it")
        return C.Name("it", C.Ref("local", loc[0] if loc else 0), line=line)

    # ---- pre-scan ----------------------------------------------------------------------
    def prescan(self) -> None:
        depth, i, t = 0, 0, self.t
        line_start = True
        in_variant = False
        while i < len(t):
            tok = t[i]
            if tok.kind == "INDENT":
                depth += 1
            elif tok.kind == "DEDENT":
                depth -= 1
                if depth == 0:
                    in_variant = False
            if tok.kind in ("INDENT", "DEDENT"):
                i += 1
                continue
            if tok.kind == "NEWLINE":
                line_start = True
                i += 1
                continue
            elif line_start and tok.kind == "NAME":
                v = tok.value
                n1, n2 = t[min(i + 1, len(t) - 1)], t[min(i + 2, len(t) - 1)]
                if depth == 0:
                    if v in ("to", "def") and n1.kind == "NAME":
                        self.defs.setdefault(n1.value, "func")
                    elif v in ("a", "an") and n1.kind == "NAME" and n1.value[:1].isupper():
                        j = i + 2
                        while j < len(t) and t[j].kind not in ("NEWLINE", "EOF") and not t[j].is_word("has", "is"):
                            j += 1
                        self.scan_plural(i, n1.value)
                        if j < len(t) and t[j].is_word("is"):
                            self.defs[n1.value] = "variant"
                            in_variant = True
                        else:
                            self.defs[n1.value] = "record"
                            self.scan_fields(j)
                    elif v == "record" and n1.kind == "NAME":
                        self.defs[n1.value] = "record"
                        self.scan_plural(i, n1.value)
                        self.scan_fields(i)
                    elif v == "var" and n1.is_word("record") and n2.kind == "NAME":
                        self.defs[n2.value] = "record"
                        self.scan_fields(i)
                    elif v == "variant" and n1.kind == "NAME":
                        self.defs[n1.value] = "variant"
                        self.scan_plural(i, n1.value)
                        in_variant = True
                    elif v == "ruleset" and n1.kind == "NAME":
                        self.defs[n1.value] = "ruleset"
                    elif v == "let" and n1.kind == "NAME":
                        self.defs.setdefault(n1.value, "const")
                elif depth == 1 and in_variant and v not in RESERVED_SET:
                    self.defs[v] = "case"
                    self.scan_fields(i)
            line_start = False
            i += 1

    def scan_plural(self, i: int, name: str) -> None:
        t, j = self.t, i
        self.plural_names[name] = plural_of(name)
        while j + 3 < len(t) and t[j].kind not in ("NEWLINE", "EOF"):
            if t[j].is_op("(") and t[j + 1].is_word("plural") and t[j + 2].kind == "NAME":
                self.plural_names[name] = t[j + 2].value
                return
            j += 1

    def scan_fields(self, j: int) -> None:
        t = self.t
        while j + 2 < len(t) and t[j].kind not in ("NEWLINE", "EOF"):
            if t[j].is_word("a", "an") and t[j + 1].kind == "NAME" and t[j + 2].is_op("("):
                self.fields_known.add(t[j + 1].value)
            if t[j].kind == "NAME" and t[j + 1].is_op(":") and j > 0 and t[j - 1].is_op("(", ","):
                self.fields_known.add(t[j].value)
            j += 1

    # ---- module ------------------------------------------------------------------------
    def parse_module(self, default_name: str = "main") -> C.Module:
        self.prescan()
        while self.cur.kind == "NEWLINE":
            self.adv()
        name, edition = default_name, None
        uses: list[C.Use] = []
        needs: tuple[C.EffItem, ...] = ()
        dialects: tuple[str, ...] = ()
        has_header = False
        order = ["module", "edition", "use", "needs", "dialect"]
        seen = -1
        trivia: list[Any] = []
        body: list[Any] = []
        while True:
            tok = self.cur
            kind = None
            if self.at("module"):
                kind = "module"
            elif self.at("edition") and self.nxt().kind == "INT":
                kind = "edition"
            elif self.at("use"):
                kind = "use"
            elif self.at("needs"):
                kind = "needs"
            elif self.at("dialect") and not self.line_ends_with_colon():
                kind = "dialect"
            if kind is None:
                break
            k = order.index(kind)
            if k < seen or (k == seen and kind != "use"):
                raise SayError("E0702", tok.line, tok.col, at_line=self.line_text(tok.line))
            seen = k
            has_header = True
            self.adv()
            if kind == "module":
                name = self.qname()
            elif kind == "edition":
                edition = int(self.adv().value)
            elif kind == "use":
                uses.append(self.use_line(tok))
            elif kind == "needs":
                needs = self.effect_row()
            else:
                ds = [self.qname()]
                while self.eat_op(","):
                    ds.append(self.qname())
                for d in ds:
                    if d in V01_DIALECTS:
                        raise SayError(
                            "E1013",
                            tok.line,
                            tok.col,
                            construct=f"dialect `{d}`",
                            profile="v0.1",
                            version="v0",
                        )
                    if d != "strict":
                        raise SayError("E0706", tok.line, tok.col, d=d, list="strict")
                dialects = tuple(sorted(ds))
            self.end_line()
        self.dialects = dialects
        if edition is None:
            if "strict" in dialects:
                raise SayError("E1012", 1, 1)
            if has_header:
                self.sink.warn("W1012", 1, 1)
            edition = 0
        pending: list[Any] = []
        while self.cur.kind != "EOF":
            if self.cur.kind == "NEWLINE":
                self.adv()
                continue
            if self.cur.kind == "NOTE":
                pending.append(self.adv().value)
                self.end_line()
                continue
            ctok = self.cur
            if self.at("module", "use", "needs") or (self.at("edition") and self.nxt().kind == "INT"):
                raise SayError("E0702", ctok.line, ctok.col, at_line=self.line_text(ctok.line))
            self.counter = 0
            item = self.top_item()
            for note in pending:
                trivia.append((len(body), "note", note))
            pending = []
            body.append(item)
        for note in pending:
            trivia.append((len(body), "note", note))
        mod = C.Module(
            name,
            edition,
            tuple(sorted(uses, key=lambda u: u.path)),
            needs,
            dialects,
            tuple(body),
            line=1,
        )
        mod = finish(mod, self.sigs)
        return replace(mod, trivia=tuple(trivia), has_header=has_header)

    def line_ends_with_colon(self) -> bool:
        j = self.p
        while self.t[j].kind not in ("NEWLINE", "EOF"):
            j += 1
        return self.t[j - 1].is_op(":")

    def qname(self) -> str:
        parts = [self.word("a module name")]
        while self.at_op(".") and self.nxt().kind == "NAME":
            self.adv()
            parts.append(self.word())
        return ".".join(parts)

    def use_line(self, tok: Tok) -> C.Use:
        if self.at("python", "c", "wasm"):
            raise SayError(
                "E1013",
                tok.line,
                tok.col,
                construct=f"`use {self.cur.value}`",
                profile="v0.1",
                version="v0",
            )
        path = self.qname()
        names: tuple[str, ...] | None = None
        alias = None
        if self.eat_op(":"):
            if self.at_op("*"):
                raise SayError("E0305", tok.line, tok.col, module=path)
            ns = [self.word()]
            while self.eat_op(","):
                ns.append(self.word())
            names = tuple(ns)
            for n in ns:
                self.defs[n] = "import"
        if self.eat("as"):
            alias = self.word()
        self.modules.add(alias or path.split(".")[-1])
        return C.Use(path, names, alias, None, line=tok.line)

    def effect_row(self) -> tuple[C.EffItem, ...]:
        items = [self.effect_item()]
        while True:
            if self.at("and") and self.nxt().kind == "NAME" and self.nxt().value in EFFECTS:
                self.adv()
            elif self.at_op(",") and self.nxt().kind == "NAME" and self.nxt().value in EFFECTS:
                self.adv()
            else:
                break
            items.append(self.effect_item())
        seen = set()
        for it in items:
            if it.effect in seen:
                raise SayError("E0407", self.cur.line, name=it.effect, decl="needs")
            seen.add(it.effect)
        return tuple(sorted(items, key=lambda e: e.effect))

    def effect_item(self) -> C.EffItem:
        tok = self.cur
        eff = self.word("an effect name")
        if eff not in EFFECTS:
            raise SayError(
                "E1013",
                tok.line,
                tok.col,
                construct=f"the user effect `{eff}`",
                profile="v0.1",
                version="v0",
            )
        narrow: list[C.Narrow] = []
        if self.at("limited") and self.nxt().is_word("to"):
            self.adv()
            self.adv()
            narrow.append(C.Narrow("limited-to", self.pc_arg()))
            if self.at_op(",") and self.nxt().is_word("read"):
                self.adv()
                self.adv()
                self.expect("only")
                narrow.append(C.Narrow("read-only"))
        return C.EffItem(eff, tuple(narrow))

    # ---- top-level items ---------------------------------------------------------------
    def top_item(self) -> Any:
        tok = self.cur
        v = tok.value if tok.kind == "NAME" else None
        if v == "to":
            return self.func_w()
        if v == "def" and self.nxt().kind == "NAME":
            return self.func_s()
        if v in ("a", "an") and self.nxt().kind == "NAME" and str(self.nxt().value)[:1].isupper():
            return self.data_w()
        if v == "record" or (v == "var" and self.nxt().is_word("record")):
            return self.record_s()
        if v == "variant" and self.nxt().kind == "NAME":
            return self.variant_s()
        if v == "ruleset":
            return self.ruleset()
        if v == "check":
            st = self.check_decl()
            self.end_line()
            return st
        if v == "let":
            st = self.let_stmt(top=True)
            self.end_line()
            return st
        if v in ("role", "effect", "dialect") or (tok.kind == "NAME" and self.nxt().is_word("plays")):
            what = "plays" if self.nxt().is_word("plays") else v
            raise SayError(
                "E1013",
                tok.line,
                tok.col,
                construct=f"`{what}` declarations",
                profile="v0.1",
                version="v0",
            )
        if v == "rewrite" or (v is None and self.line_has_op("=>")):
            raise SayError(
                "E0903",
                tok.line,
                tok.col,
                rule="A rule appears outside a ruleset",
                what="This rule appears outside a `ruleset` block.",
            )
        raise SayError(
            "E0130",
            tok.line,
            tok.col,
            token=self.describe(tok),
            expected="a declaration, a note, a check or an immutable top-level `let`",
            hint="put it inside `to main`",
        )

    def line_has_op(self, op: str) -> bool:
        j = self.p
        while self.t[j].kind not in ("NEWLINE", "EOF"):
            if self.t[j].is_op(op):
                return True
            j += 1
        return False

    def func_w(self) -> C.Func:
        tok = self.expect("to")
        name = self.def_name("function")
        params: list[C.Param] = []
        while not (self.at("giving") or self.at_op(",", ":")):
            lead = None
            if self.cur.kind == "NAME" and self.cur.value in LEADS and self.nxt().kind == "NAME":
                lead = str(self.adv().value)
            ptok = self.cur
            pname = self.word("a parameter name")
            ptype, default = None, None
            if self.eat_op("("):
                ptype = self.type_any()
                if self.eat_op(","):
                    self.expect("default")
                    default = self.expr()
                self.expect_op(")")
            params.append(C.Param(pname, lead, ptype, default))
            self.check_case(pname, ptok, False, "parameter")
        result = self.type_any() if self.eat("giving") else None
        effects: tuple[C.EffItem, ...] = ()
        fails: list[str] = []
        generics: list[C.TParam] = []
        while self.eat_op(","):
            if self.eat("needs"):
                effects = self.effect_row()
            elif self.at("may"):
                self.adv()
                self.expect("fail")
                self.expect("with")
                fails.append(self.word("a problem kind"))
                while self.eat("and"):
                    fails.append(self.word("a problem kind"))
            elif self.at("for") and self.nxt().is_word("any"):
                self.adv()
                self.adv()
                generics.append(C.TParam(self.word("a type variable")))
                while self.eat("and"):
                    generics.append(C.TParam(self.word("a type variable")))
                if self.at("that"):
                    raise SayError(
                        "E1013",
                        self.cur.line,
                        self.cur.col,
                        construct="`that plays` constraints",
                        profile="v0.1",
                        version="v0",
                    )
            elif self.at("explained"):
                raise SayError(
                    "E1013",
                    self.cur.line,
                    self.cur.col,
                    construct="`explained as`",
                    profile="v0.1",
                    version="v0",
                )
            else:
                raise self.fail("`needs`, `may fail with` or `for any`")
        self.expect_op(":")
        return self.func_body(tok, name, params, result, effects, fails, generics)

    def func_s(self) -> C.Func:
        tok = self.adv()
        name = self.def_name("function")
        generics: list[C.TParam] = []
        if self.eat_op("["):
            generics.append(C.TParam(self.word("a type variable")))
            while self.eat_op(","):
                generics.append(C.TParam(self.word("a type variable")))
            self.expect_op("]")
        self.expect_op("(")
        params: list[C.Param] = []
        while not self.at_op(")"):
            lead = None
            if self.cur.kind == "NAME" and self.cur.value in LEADS and self.nxt().kind == "NAME":
                lead = str(self.adv().value)
            ptok = self.cur
            pname = self.word("a parameter name")
            ptype = self.type_s() if self.eat_op(":") else None
            default = self.expr() if self.eat_op("=") else None
            params.append(C.Param(pname, lead, ptype, default))
            self.check_case(pname, ptok, False, "parameter")
            if not self.eat_op(","):
                break
        self.expect_op(")")
        result = self.type_s() if self.eat_op("->") else None
        effects: tuple[C.EffItem, ...] = ()
        if self.eat("needs"):
            effects = self.effect_row()
        fails: list[str] = []
        if self.eat("fails"):
            fails.append(self.word("a problem kind"))
            while self.eat_op(","):
                fails.append(self.word("a problem kind"))
        self.expect_op(":")
        return self.func_body(tok, name, params, result, effects, fails, generics)

    def def_name(self, kind: str) -> str:
        tok = self.cur
        name = self.word(f"a {kind} name")
        self.check_case(name, tok, kind in ("record", "variant"), kind)
        if name in CONTEXTUAL_SET and self.sink is not None and not self.file.endswith("prelude"):
            self.sink.warn("W0114", tok.line, tok.col, word=name)
        return name

    def check_case(self, name: str, tok: Tok, upper: bool, kind: str) -> None:
        if upper != name[:1].isupper():
            sugg = (name[:1].upper() if upper else name[:1].lower()) + name[1:]
            raise SayError("E0126", tok.line, tok.col, word=name, kind=kind, suggested=sugg)

    def func_body(
        self,
        tok: Tok,
        name: str,
        params: list[C.Param],
        result: Any,
        effects: tuple[C.EffItem, ...],
        fails: list[str],
        generics: list[C.TParam],
    ) -> C.Func:
        seen_names: set[str] = set()
        seen_leads: set[str] = set()
        named_or_slot = False
        for i, prm in enumerate(params):
            if prm.name in seen_names or (prm.slot and prm.slot != "with" and prm.slot in seen_leads):
                raise SayError("E0407", tok.line, tok.col, name=prm.name, decl=name)
            seen_names.add(prm.name)
            if prm.slot:
                seen_leads.add(prm.slot)
            if prm.slot == "of" and i != 0:
                raise SayError(
                    "E0407",
                    tok.line,
                    tok.col,
                    name="of",
                    decl=name,
                    what=f"`of` may only lead the first parameter of `{name}`.",
                )
            if prm.slot in SLOT_WORDS or prm.slot == "with":
                named_or_slot = True
            elif named_or_slot:
                raise SayError(
                    "E0407",
                    tok.line,
                    tok.col,
                    name=prm.name,
                    decl=name,
                    what=f"Positional parameter `{prm.name}` comes after a slot or named parameter in `{name}`.",
                )
        gnames = {g.name for g in generics}
        params = [replace(p_, type=tvars(p_.type, gnames)) for p_ in params]
        result = tvars(result, gnames)
        self.in_func = True
        with self.scope("func"):
            for prm in params:
                self.bind(prm.name, False, tok.line)
            body = self.block()
        self.in_func = False
        self.sigs[name] = [(p_.slot, p_.name, p_.default is not None) for p_ in params]
        return C.Func(
            name,
            tuple(params),
            result,
            effects,
            tuple(sorted(set(fails))),
            tuple(generics),
            body,
            line=tok.line,
        )

    def data_w(self) -> Any:
        tok = self.adv()
        name = self.def_name("record")
        tparams: list[C.TParam] = []
        if self.eat("of"):
            tparams.append(C.TParam(self.word("a type variable")))
            while self.eat("and"):
                tparams.append(C.TParam(self.word("a type variable")))
        plural, declared = self.plural_opt(name)
        tvs = {t.name for t in tparams}
        if self.eat("is"):
            self.expect("one")
            self.expect("of")
            self.expect_op(":")
            self.end_line()
            cases = self.cases(tvs)
            return C.VariantDef(name, plural, tuple(tparams), tuple(cases), line=tok.line, plural_declared=declared)
        self.expect("has")
        fields: list[C.FieldDef] = []
        invariants: list[Any] = []
        changeable = False
        with self.scope("record"):
            if self.eat_op(":"):
                self.end_line()
                if self.cur.kind != "INDENT":
                    raise SayError("E0131", self.cur.line, 1, what="The record block is empty.", opener="has:")
                self.adv()
                while self.cur.kind != "DEDENT":
                    if self.eat("changeable"):
                        changeable = True
                    elif self.eat("where"):
                        invariants.append(self.expr())
                    else:
                        fields.append(self.field_w(tvs))
                    self.end_line()
                self.adv()
            else:
                fields.append(self.field_w(tvs))
                while True:
                    if self.at("and") and self.nxt().is_word("a", "an"):
                        self.adv()
                    elif self.at_op(",") and self.nxt().is_word("a", "an"):
                        self.adv()
                    else:
                        break
                    fields.append(self.field_w(tvs))
                while self.eat_op(","):
                    if self.eat("changeable"):
                        changeable = True
                    elif self.eat("where"):
                        invariants.append(self.expr())
                    else:
                        raise self.fail("`changeable` or `where …`")
                self.end_line()
        self.check_fields(fields, name, tok)
        return C.RecordDef(
            name,
            plural,
            tuple(tparams),
            tuple(fields),
            tuple(invariants),
            changeable,
            line=tok.line,
            plural_declared=declared,
        )

    def check_fields(self, fields: list[C.FieldDef], decl: str, tok: Tok) -> None:
        seen: set[str] = set()
        for f in fields:
            if f.name in seen:
                raise SayError("E0407", tok.line, tok.col, name=f.name, decl=decl)
            seen.add(f.name)

    def plural_opt(self, name: str) -> tuple[str, bool]:
        if self.at_op("(") and self.nxt().is_word("plural"):
            self.adv()
            self.adv()
            pl = self.word("a plural")
            self.expect_op(")")
            return pl, True
        return plural_of(name), False

    def field_w(self, tvs: set[str]) -> C.FieldDef:
        if not self.eat("a", "an"):
            raise self.fail("`a` or `an` before a field name")
        ftok = self.cur
        fname = self.word("a field name")
        self.check_case(fname, ftok, False, "field")
        self.expect_op("(")
        ftype = tvars(self.type_any(), tvs)
        default = None
        if self.eat_op(","):
            self.expect("default")
            default = self.expr()
        self.expect_op(")")
        self.bind(fname, False, ftok.line, check=False)
        return C.FieldDef(fname, ftype, default)

    def field_s(self, tvs: set[str]) -> C.FieldDef:
        ftok = self.cur
        fname = self.word("a field name")
        self.check_case(fname, ftok, False, "field")
        self.expect_op(":")
        ftype = tvars(self.type_s(), tvs)
        default = self.expr() if self.eat_op("=") else None
        self.bind(fname, False, ftok.line, check=False)
        return C.FieldDef(fname, ftype, default)

    def record_s(self) -> C.RecordDef:
        tok = self.cur
        changeable = self.eat("var")
        self.expect("record")
        name = self.def_name("record")
        tparams: list[C.TParam] = []
        if self.eat_op("["):
            tparams.append(C.TParam(self.word()))
            while self.eat_op(","):
                tparams.append(C.TParam(self.word()))
            self.expect_op("]")
        plural, declared = self.plural_opt(name)
        tvs = {t.name for t in tparams}
        fields: list[C.FieldDef] = []
        invariants: list[Any] = []
        with self.scope("record"):
            self.expect_op("(")
            fields.append(self.field_s(tvs))
            while self.eat_op(","):
                fields.append(self.field_s(tvs))
            self.expect_op(")")
            while self.eat("where"):
                invariants.append(self.expr())
                self.eat_op(",")
        self.end_line()
        self.check_fields(fields, name, tok)
        return C.RecordDef(
            name,
            plural,
            tuple(tparams),
            tuple(fields),
            tuple(invariants),
            changeable,
            line=tok.line,
            plural_declared=declared,
        )

    def variant_s(self) -> C.VariantDef:
        tok = self.adv()
        name = self.def_name("variant")
        tparams: list[C.TParam] = []
        if self.eat_op("["):
            tparams.append(C.TParam(self.word()))
            while self.eat_op(","):
                tparams.append(C.TParam(self.word()))
            self.expect_op("]")
        plural, declared = self.plural_opt(name)
        self.expect_op(":")
        self.end_line()
        cases = self.cases({t.name for t in tparams})
        return C.VariantDef(name, plural, tuple(tparams), tuple(cases), line=tok.line, plural_declared=declared)

    def cases(self, tvs: set[str]) -> list[C.CaseDef]:
        if self.cur.kind != "INDENT":
            raise SayError(
                "E0131",
                self.cur.line,
                1,
                what="A variant needs at least one case.",
                opener="is one of:",
            )
        self.adv()
        cases: list[C.CaseDef] = []
        seen: set[str] = set()
        while self.cur.kind != "DEDENT":
            ctok = self.cur
            cname = self.word("a case name")
            self.check_case(cname, ctok, False, "case")
            if cname in seen:
                raise SayError("E0407", ctok.line, ctok.col, name=cname, decl="the variant")
            seen.add(cname)
            fields: list[C.FieldDef] = []
            with self.scope("record"):
                if self.eat("with"):
                    fields.append(self.field_w(tvs))
                    while (self.at("and") or self.at_op(",")) and self.nxt().is_word("a", "an"):
                        self.adv()
                        fields.append(self.field_w(tvs))
                elif self.eat_op("("):
                    fields.append(self.field_s(tvs))
                    while self.eat_op(","):
                        fields.append(self.field_s(tvs))
                    self.expect_op(")")
            self.check_fields(fields, cname, ctok)
            cases.append(C.CaseDef(cname, tuple(fields)))
            self.end_line()
        self.adv()
        return cases

    def ruleset(self) -> C.Ruleset:
        tok = self.adv()
        name = self.word("a ruleset name")
        self.expect_op(":")
        self.end_line()
        if self.cur.kind != "INDENT":
            raise SayError("E0131", self.cur.line, 1, what="The ruleset has no rules.", opener="ruleset")
        self.adv()
        rules = []
        while self.cur.kind != "DEDENT":
            if self.cur.kind == "NEWLINE":
                self.adv()
                continue
            rules.append(self.rule_line())
            self.end_line()
        self.adv()
        return C.Ruleset(name, tuple(rules), line=tok.line)

    def rule_line(self) -> C.Rule:
        tok = self.cur
        words = self.eat("rewrite")
        self.patvars = {}
        self.quote += 1
        self.nolambda = True
        try:
            lhs = self.expr()
            bound = dict(self.patvars)
            if words:
                self.expect("as")
            else:
                self.expect_op("=>")
            self.nolambda = False
            rhs = self.expr()
            extra = [v for v in self.patvars if v not in bound]
            if extra:
                raise SayError("E0902", tok.line, tok.col, v=extra[0])
            guard = None
            if (words and self.eat("when")) or (not words and self.eat("if")):
                guard = self.expr()
        finally:
            self.patvars = None
            self.quote -= 1
            self.nolambda = False
        return C.Rule(C.PQuote(lhs), rhs, guard, line=tok.line)

    def check_decl(self, inner: bool = False) -> C.Check:
        tok = self.adv()
        if self.in_func and not inner:
            raise SayError("E1004", tok.line, tok.col, fn="this function")
        if self.cur.kind == "TEXT":
            label = "".join(p for p in self.adv().value if isinstance(p, str))
            self.expect_op(":")
            body = self.block(checks=True)
            return C.Check(label, None, "holds", None, body, line=tok.line)
        words = self.eat("that")
        subject = self.with_stop({"fails"}, self.expr)
        if self.at("fails"):
            self.adv()
            if words:
                self.expect("with")
            kind = self.word("a problem kind")
            return C.Check(None, subject, "fails-with", C.SymLit(kind), None, line=tok.line)
        return check_of(subject, tok.line)

    # ---- helpers for contextual parsing ------------------------------------------------
    def with_stop(self, words: set[str], fn: Any, *args: Any) -> Any:
        saved = self.stop
        self.stop = set(words)
        try:
            return fn(*args)
        finally:
            self.stop = saved

    def logical_line_ops(self) -> list[Tok]:
        j, out = self.p, []
        while self.t[j].kind not in ("NEWLINE", "EOF", "INDENT", "DEDENT"):
            out.append(self.t[j])
            j += 1
        return out

    def starts_operand(self, tok: Tok, nxt: Tok | None = None) -> bool:
        if tok.kind in ("INT", "DEC", "APPROX", "TEXT", "SYM", "DUR", "PATVAR"):
            return True
        if tok.kind == "OP":
            if tok.value in ("(", "[", "{"):
                return tok.spaced
            if tok.value in ("`", "~"):
                return True
            if tok.value == "-" and tok.spaced and nxt is not None and not nxt.spaced:
                return nxt.kind in ("INT", "DEC", "APPROX", "NAME", "DUR") or nxt.is_op("(")
            return False
        if tok.kind != "NAME" or tok.value in self.stop:
            return False
        v = tok.value
        if v in RESERVED_SET:
            return v in VALUE_RESERVED or v in ("a", "an", "each")
        return v not in OPWORDS and v not in ("where", "fails", "exclusive", "descending")

    def is_callee(self, name: str) -> bool:
        if self.quote or self.lookup(name) is not None:
            return False
        kind = self.defs.get(name)
        if kind in ("func", "import"):
            return True
        return name in BUILTIN_NAMES and name not in ("empty-set", "Pair")

    def text_of(self, a: int, b: int) -> str:
        out: list[str] = []
        for tok in self.t[a:b]:
            raw = tok.raw or (str(tok.value) if tok.value is not None else "")
            if tok.kind == "TEXT" and not tok.raw:
                raw = '"…"'
            if out and tok.spaced and tok.kind != "POSS":
                out.append(" ")
            out.append(raw)
        return "".join(out)

    # ---- blocks and statements ---------------------------------------------------------
    def block(self, checks: bool = False) -> C.Block:
        self.end_line()
        if self.cur.kind != "INDENT":
            raise SayError("E0131", self.cur.line, 1, what="Expected an indented block.", opener=":")
        self.adv()
        stmts: list[Any] = []
        trivia: list[Any] = []
        with self.scope():
            while self.cur.kind not in ("DEDENT", "EOF"):
                if self.cur.kind == "NEWLINE":
                    self.adv()
                    continue
                if self.cur.kind == "NOTE":
                    trivia.append((len(stmts), "note", self.adv().value))
                    self.end_line()
                    continue
                st, compound = self.stmt(checks)
                stmts.append(st)
                if not compound:
                    self.end_line()
        if self.cur.kind == "DEDENT":
            self.adv()
        return C.Block(tuple(stmts), trivia=tuple(trivia))

    def stmt(self, checks: bool = False) -> tuple[Any, bool]:
        tok = self.cur
        v = tok.value if tok.kind == "NAME" else None
        line = tok.line
        if v in ("let", "var"):
            res: tuple[Any, bool] = self.let_stmt()
            return res
        if v == "set" and self.nxt().kind == "NAME" and self.nxt(2).is_word("to"):
            self.adv()
            name_tok = self.cur
            name = self.word()
            self.expect("to")
            return self.rebind(name, name_tok, self.expr(), line), False
        if v == "change" and self.nxt().is_word("the"):
            self.adv()
            self.adv()
            fld = self.word("a field name")
            self.expect("of")
            target = self.with_stop({"to"}, self.expr)
            self.expect("to")
            return C.SetField(target, fld, self.expr(), line=line), False
        if v in ("give", "return"):
            return self.return_stmt(tok)
        if v in ("stop", "break", "skip", "continue"):
            self.adv()
            if not self.loops:
                raise SayError("E0130", line, tok.col, token=v, try_="use it inside `for` or `while`")
            return (C.Stop(line=line) if v in ("stop", "break") else C.Skip(line=line)), False
        if v == "if":
            return self.if_stmt(), True
        if v == "match":
            return self.match_stmt(), True
        if v == "for":
            return self.for_stmt(), True
        if v == "repeat":
            return self.repeat_stmt(), True
        if v == "while":
            self.adv()
            cond = self.expr()
            self.expect_op(":")
            self.loops += 1
            body = self.block()
            self.loops -= 1
            return C.While(cond, body, line=line), True
        if v == "with" and self.nxt().kind == "NAME" and self.nxt(2).is_word("limited"):
            return self.with_stmt(), True
        if v == "together" and self.nxt().is_op(":"):
            return self.together(), True
        if v == "within":
            self.adv()
            limit = self.pc_arg()
            self.expect_op(":")
            return C.Within(limit, self.block(), line=line), True
        if v == "check":
            return self.check_decl(inner=checks), False
        if v == "add" and self.is_add_stmt():
            self.adv()
            item = self.with_stop({"to"}, self.pc_arg)
            self.expect("to")
            name_tok = self.cur
            name = self.word()
            target = C.Name(name, self.ref_for(name), line=line)
            return self.rebind(name, name_tok, op_call("added", [target, item], line), line), False
        if self.at_block_expr():
            return C.ExprStmt(self.block_expr(), line=line), True
        return self.assign_or_expr(tok, v)

    def assign_or_expr(self, tok: Tok, v: Any) -> tuple[Any, bool]:
        line = tok.line
        if tok.kind == "NAME" and self.nxt().is_op(":=", "+="):
            name = self.word()
            op = self.adv().value
            if op == ":=":
                if self.at_block_expr():
                    return self.rebind(name, tok, self.block_expr(), line), True
                return self.rebind(name, tok, self.expr(), line), False
            target = C.Name(name, self.ref_for(name), line=line)
            return self.rebind(name, tok, op_call("added", [target, self.expr()], line), line), False
        if any(o.is_op(":=") for o in self.logical_line_ops()):
            target = self.postfix()
            if not isinstance(target, C.Get):
                raise self.fail("a field on the left of `:=`")
            self.expect_op(":=")
            return C.SetField(target.target, target.field, self.expr(), line=line), False
        if v in ("def", "record", "variant", "ruleset"):
            raise SayError("E0130", line, tok.col, token=v, try_="declarations belong at the top level")
        return C.ExprStmt(self.expr(), line=line), False

    def return_stmt(self, tok: Tok) -> tuple[Any, bool]:
        self.adv()
        line = tok.line
        if tok.value == "give":
            self.expect("back")
        if not self.in_func:
            raise SayError("E0130", line, tok.col, token=tok.value, try_="use it inside a function")
        if self.cur.kind in ("NEWLINE", "EOF", "DEDENT"):
            return C.Return(None, line=line), False
        if self.at_block_expr():
            return C.Return(self.block_expr(), line=line), True
        return C.Return(self.expr(), line=line), False

    def repeat_stmt(self) -> C.For:
        tok = self.adv()
        n = self.with_stop({"times"}, self.expr)
        self.expect("times")
        self.expect_op(":")
        self.loops += 1
        body = self.block()
        self.loops -= 1
        src = op_call("range", [C.Lit("integer", 1), n], tok.line)
        return C.For(C.PWild(), src, body, line=tok.line)

    def with_stmt(self) -> C.WithCap:
        tok = self.adv()
        eff = self.word("an effect name")
        if eff not in EFFECTS:
            raise SayError(
                "E1013",
                tok.line,
                tok.col,
                construct=f"the user effect `{eff}`",
                profile="v0.1",
                version="v0",
            )
        self.adv()
        self.expect("to")
        narrow = [C.Narrow("limited-to", self.pc_arg())]
        if self.at_op(",") and self.nxt().is_word("read"):
            self.adv()
            self.adv()
            self.expect("only")
            narrow.append(C.Narrow("read-only"))
        self.expect_op(":")
        cap = C.Name(eff, C.Ref("builtin", eff), line=tok.line)
        return C.WithCap(cap, tuple(narrow), self.block(), line=tok.line)

    def is_add_stmt(self) -> bool:
        ops = self.logical_line_ops()
        return len(ops) >= 4 and ops[-2].is_word("to") and ops[-1].kind == "NAME"

    def rebind(self, name: str, tok: Tok, value: Any, line: int) -> C.Rebind:
        loc = self.lookup(name)
        if loc is None or not loc[1]:
            raise SayError("E0302", tok.line, tok.col, name=name)
        return C.Rebind(C.Name(name, C.Ref("local", loc[0]), line=tok.line), value, line=line)

    def let_stmt(self, top: bool = False) -> Any:
        tok = self.adv()
        mutable = tok.value == "var"
        if top and mutable:
            raise SayError("E0130", tok.line, tok.col, token="var", try_="top-level bindings are immutable")
        pstart = self.p
        pat, names = self.with_stop({"be"}, self.pattern, "bind")
        ptext = self.text_of(pstart, self.p)
        ptype = self.type_any() if self.eat_op(":") else None
        compound = False
        if self.at_op("="):
            self.adv()
        elif not mutable:
            self.expect("be")
        else:
            raise self.fail("`=`")
        if self.at_block_expr():
            value: Any = self.block_expr()
            compound = True
        else:
            value = self.expr()
        if not mutable and self.at_op(",") and self.nxt().is_word("changeable"):
            if top:
                raise SayError(
                    "E0130",
                    tok.line,
                    tok.col,
                    token="changeable",
                    try_="top-level bindings are immutable",
                )
            self.adv()
            self.adv()
            mutable = True
        if not irrefutable(pat):
            raise SayError("E0905", tok.line, tok.col, pattern=ptext)
        if top:
            for n in names:
                self.defs[n] = "const"
            pat = bind_refs(pat, {n: C.Ref("def", n) for n in names})
        else:
            pat = bind_refs(pat, {n: C.Ref("local", self.bind(n, mutable, tok.line)) for n in names})
        node = C.Bind(pat, value, mutable, ptype, line=tok.line)
        return node if top else (node, compound)

    def if_stmt(self) -> C.If:
        tok = self.adv()
        branches = [C.Branch(self.expr(), self.colon_block())]
        else_ = None
        while True:
            if self.at("otherwise") and self.nxt().is_word("if"):
                self.adv()
                self.adv()
            elif self.at("elif"):
                self.adv()
            else:
                break
            branches.append(C.Branch(self.expr(), self.colon_block()))
        if self.at("otherwise", "else") and self.nxt().is_op(":"):
            self.adv()
            else_ = self.colon_block()
        return C.If(tuple(branches), else_, line=tok.line)

    def colon_block(self) -> C.Block:
        self.expect_op(":")
        return self.block()

    def match_stmt(self) -> C.Match:
        tok = self.adv()
        subject = self.expr()
        self.expect_op(":")
        self.end_line()
        if self.cur.kind != "INDENT":
            raise SayError("E0131", self.cur.line, 1, what="A match needs cases.", opener="match")
        self.adv()
        cases: list[C.MCase] = []
        else_ = None
        while self.cur.kind not in ("DEDENT", "EOF"):
            if self.cur.kind == "NEWLINE":
                self.adv()
                continue
            if self.at("otherwise", "else"):
                self.adv()
                else_ = self.colon_block()
                continue
            words = self.at("when")
            if not self.eat("when", "case"):
                raise self.fail("`when` or `case`")
            with self.scope():
                pat, names = self.with_stop({"if"}, self.pattern, "match")
                refs = {n: C.Ref("local", self.bind(n, False, tok.line)) for n in names}
                pat = bind_refs(pat, refs)
                guard = None
                if words and self.at_op(",") and self.nxt().is_word("if"):
                    self.adv()
                    self.adv()
                    guard = self.expr()
                elif not words and self.eat("if"):
                    guard = self.expr()
                body = self.colon_block()
            cases.append(C.MCase(pat, guard, body))
        self.adv()
        return C.Match(subject, tuple(cases), else_, line=tok.line)

    def for_stmt(self) -> C.For:
        tok = self.adv()
        words = self.eat("each")
        with self.scope():
            pstart = self.p
            pat, names = self.with_stop({"in", "received"}, self.pattern, "bind")
            ptext = self.text_of(pstart, self.p)
            if words and self.eat("received"):
                self.expect("from")
                source = op_call("received", [self.expr()], tok.line)
            else:
                self.expect("in")
                source = self.expr()
            if not irrefutable(pat):
                raise SayError("E0905", tok.line, tok.col, pattern=ptext)
            pat = bind_refs(pat, {n: C.Ref("local", self.bind(n, False, tok.line)) for n in names})
            self.expect_op(":")
            self.loops += 1
            body = self.block()
            self.loops -= 1
        return C.For(pat, source, body, line=tok.line)

    def together(self) -> C.Concurrent:
        tok = self.adv()
        self.expect_op(":")
        self.end_line()
        if self.cur.kind != "INDENT":
            raise SayError("E0131", self.cur.line, 1, what="`together:` needs children.", opener="together:")
        self.adv()
        children: list[C.Child] = []
        while self.cur.kind not in ("DEDENT", "EOF"):
            if self.cur.kind == "NEWLINE":
                self.adv()
                continue
            if self.at("let", "var"):
                raise SayError("E0604", self.cur.line, self.cur.col)
            with self.scope():
                st, compound = self.stmt()
            if not compound:
                self.end_line()
            children.append(C.Child(None, C.Block((st,))))
        self.adv()
        return C.Concurrent("together", tuple(children), line=tok.line)

    def at_block_expr(self) -> bool:
        if (
            self.at("all", "first")
            and self.nxt().is_word("of")
            and self.nxt(2).is_op(":")
            and self.nxt(3).kind == "NEWLINE"
        ):
            return True
        return self.at("all-of", "first-of") and self.nxt().is_op(":")

    def block_expr(self) -> C.Concurrent:
        tok = self.adv()
        mode = "all" if str(tok.value).startswith("all") else "first"
        if tok.value in ("all", "first"):
            self.expect("of")
        self.expect_op(":")
        self.end_line()
        if self.cur.kind != "INDENT":
            raise SayError("E0131", self.cur.line, 1, what="The block needs children.", opener=f"{mode} of:")
        self.adv()
        children: list[C.Child] = []
        while self.cur.kind not in ("DEDENT", "EOF"):
            if self.cur.kind == "NEWLINE":
                self.adv()
                continue
            label = None
            if self.cur.kind == "NAME" and self.nxt().is_op(":"):
                label = self.word()
                self.adv()
            children.append(C.Child(label, self.expr()))
            self.end_line()
        self.adv()
        if len({c.label is not None for c in children}) > 1:
            raise SayError("E0130", tok.line, tok.col, token="label", try_="label every child or none")
        return C.Concurrent(mode, tuple(children), line=tok.line)

    # ---- expressions: P1-P6 ------------------------------------------------------------
    def expr(self) -> Any:
        e = self.absence()
        while self.at("then") or self.at_op("|>"):
            line = self.adv().line
            fn = self.callee_name()
            args: list[Any] = [e]
            slots: list[tuple[str, Any]] = []
            if self.at_op("(") and not self.cur.spaced:
                a2, s2 = self.call_args()
                args += a2
                slots += s2
            self.slot_args(slots)
            self.named_args(slots)
            e = C.Call(fn, tuple(args), tuple(slots), line=line)
        return e

    def callee_name(self) -> Any:
        tok = self.cur
        name = self.word("a function name")
        if name in self.modules and self.at_op(".") and self.nxt().kind == "NAME" and not self.lookup(name):
            self.adv()
            name = f"{name}.{self.word()}"
            return C.Name(name, C.Ref("builtin", name), line=tok.line)
        return self.name_node(name, tok.line)

    def absence(self) -> Any:
        left = self.logic_or()
        if (self.at("or") and self.nxt().is_word("else")) or self.at_op("??"):
            line = self.adv().line
            self.eat("else")
            return op_call("default", [left, thunk(self.absence())], line)
        return left

    def logic_or(self) -> Any:
        left, mixed = self.logic_and()
        any_or = False
        while (self.at("or") and not self.nxt().is_word("else")) or self.at_op("||"):
            line = self.adv().line
            right, m2 = self.logic_and()
            mixed = mixed or m2
            any_or = True
            left = op_call("or", [left, thunk(right)], line)
        if any_or and mixed:
            self.sink.warn("W0116", self.cur.line)
        return left

    def logic_and(self) -> tuple[Any, bool]:
        left = self.logic_not()
        seen = False
        while (self.at("and") and "and" not in self.stop) or self.at_op("&&"):
            line = self.adv().line
            seen = True
            left = op_call("and", [left, thunk(self.logic_not())], line)
        return left, seen

    def logic_not(self) -> Any:
        if self.at("not") or self.at_op("!"):
            line = self.adv().line
            return op_call("not", [self.logic_not()], line)
        return self.comparison(self.clause_expr)

    # ---- comparison (P6) ---------------------------------------------------------------
    CMP_OPS = ("=", "==", "!=", "<", "<=", ">", ">=", "===", "~=", "\u2261")

    def comparison(self, operand: Any) -> Any:
        start = self.p
        left = operand()
        tok = self.cur
        line = tok.line
        if (tok.kind == "OP" and tok.value in self.CMP_OPS) or (tok.is_word("in") and "in" not in self.stop):
            op = str(self.adv().value)
            if op == "~=":
                return op_call("match", [left, self.quoted_pattern(operand)], line)
            right = operand()
            if op == "\u2261":
                self.expect("using")
                rs = self.word("a ruleset name")
                return op_call("egraph-equiv", [left, right, self.name_node(rs, line)], line)
            nxt = self.cur
            if (nxt.kind == "OP" and nxt.value in self.CMP_OPS) or nxt.is_word("equals", "is", "contains", "matches"):
                op2 = str(nxt.value)
                lo_ops, hi_ops = {"<", "<="}, {">", ">="}
                if (op in lo_ops and op2 in lo_ops) or (op in hi_ops and op2 in hi_ops):
                    self.adv()
                    third = operand()
                    if op in lo_ops:
                        return self.between(right, left, third, op == "<=", op2 == "<=", line)
                    return self.between(right, third, left, op2 == ">=", op == ">=", line)
                self.chain_error(start, nxt)
            return self.sym_cmp(op, left, right, line)
        if tok.is_word("equals", "contains", "matches"):
            word = str(self.adv().value)
            if word == "matches":
                return op_call("match", [left, self.quoted_pattern(operand)], line)
            right = operand()
            self.no_chain(start)
            if word == "equals":
                return op_call("equal", [left, right], line)
            return op_call("contains", [left, right], line)
        if tok.is_word("is"):
            self.adv()
            res = self.is_tail(left, operand, line, start)
            self.no_chain(start)
            return res
        return left

    def no_chain(self, start: int) -> None:
        nxt = self.cur
        if (nxt.kind == "OP" and nxt.value in self.CMP_OPS) or nxt.is_word("is", "equals", "contains", "matches"):
            self.chain_error(start, nxt)

    def chain_error(self, start: int, nxt: Tok) -> None:
        j = self.p
        while self.t[j].kind not in ("NEWLINE", "EOF") and not self.t[j].is_op(":"):
            j += 1
        raise SayError("E0121", nxt.line, nxt.col, text=self.text_of(start, j), x="x", lo="lo", hi="hi")

    def sym_cmp(self, op: str, left: Any, right: Any, line: int) -> Any:
        if op == "!=":
            return op_call("not", [op_call("equal", [left, right], line)], line)
        if op == "in":
            return op_call("contains", [right, left], line)
        return op_call(CMP_SYM[op], [left, right], line)

    def between(self, x: Any, lo: Any, hi: Any, lo_inc: bool, hi_inc: bool, line: int) -> Any:
        slots: list[tuple[str, Any]] = []
        if not lo_inc:
            slots.append(("low-inclusive", C.Lit("truth", False)))
        if not hi_inc:
            slots.append(("high-inclusive", C.Lit("truth", False)))
        return op_call("between", [x, lo, hi], line, tuple(slots))

    def quoted_pattern(self, operand: Any) -> C.Quote:
        saved = self.patvars
        self.patvars = {} if saved is None else saved
        self.quote += 1
        try:
            e = operand()
        finally:
            self.quote -= 1
            self.patvars = saved
        return C.Quote(e)

    def is_tail(self, left: Any, operand: Any, line: int, start: int) -> Any:
        if self.at("equivalent"):
            self.adv()
            self.expect("to")
            right = self.with_stop(self.stop | {"using"}, operand)
            self.expect("using")
            rs = self.word("a ruleset name")
            return op_call("egraph-equiv", [left, right, self.name_node(rs, line)], line)
        neg = self.eat("not")
        res = self.is_core(left, operand, line, start)
        return op_call("not", [res], line) if neg else res

    def is_core(self, left: Any, operand: Any, line: int, start: int) -> Any:
        tok = self.cur
        if self.at("a", "an", "text", "anything"):
            return C.TypeTest(left, self.type_w(), line=line)
        if self.eat("nothing"):
            return C.TypeTest(left, C.TName("nothing"), line=line)
        if self.eat("in"):
            return op_call("contains", [operand(), left], line)
        pairs = {
            ("less", "than"): "less",
            ("greater", "than"): "greater",
            ("at", "least"): "greater-eq",
            ("at", "most"): "less-eq",
            ("equal", "to"): "equal",
        }
        for (w1, w2), fn in pairs.items():
            if self.at(w1) and self.nxt().is_word(w2):
                self.adv()
                self.adv()
                return op_call(fn, [left, operand()], line)
        if self.at("the") and self.nxt().is_word("same") and self.nxt(2).is_word("as"):
            for _ in range(3):
                self.adv()
            return op_call("same", [left, operand()], line)
        if self.eat("between"):
            lo = self.with_stop(self.stop | {"and"}, operand)
            self.expect("and")
            hi = operand()
            lo_inc = hi_inc = True
            if self.at_op(",") and self.nxt().is_word("exclusive"):
                self.adv()
                self.adv()
                if self.eat("above"):
                    hi_inc = False
                elif self.eat("below"):
                    lo_inc = False
                else:
                    lo_inc = hi_inc = False
            return self.between(left, lo, hi, lo_inc, hi_inc, line)
        if tok.kind == "NAME" and str(tok.value)[:1].isupper():
            return C.TypeTest(left, self.type_s(), line=line)
        if tok.kind == "NAME" and tok.value not in RESERVED_SET:
            return self.adjective(left, tok, line, start)
        raise self.fail("a comparison, a type or an adjective after `is`")

    def adjective(self, left: Any, tok: Tok, line: int, start: int) -> Any:
        adj = str(self.adv().value)
        pred = f"is-{adj}"
        if pred in self.defs or pred in BUILTIN_NAMES:
            return C.Call(self.name_node(pred, line), (left,), line=line)
        subject = self.text_of(start, self.p - 2)
        if self.lookup(adj) is not None or self.defs.get(adj) == "const":
            raise SayError("E0110", tok.line, tok.col, a=subject, b=adj)
        known = sorted(n[3:] for n in list(self.defs) + list(BUILTIN_NAMES) if n.startswith("is-"))
        raise SayError(
            "E0115",
            tok.line,
            tok.col,
            adj=adj,
            x=subject,
            suggestions=", ".join(f"`is {k}`" for k in known[:3]) or "a comparison",
        )

    # ---- postfix clauses (P7) and the cond sub-grammar ---------------------------------
    def clause_expr(self) -> Any:
        return self.clauses(self.range_expr())

    def clauses(self, e: Any) -> Any:
        while True:
            tok = self.cur
            line = tok.line
            if tok.is_word("where") and "where" not in self.stop:
                self.adv()
                e = op_call("filter", [e, self.it_lambda(self.cond, True)], line)
            elif tok.is_word("each") and "each" not in self.stop:
                self.adv()
                e = op_call("map", [e, self.it_lambda(self.cond, True)], line)
            elif tok.is_word("sorted") and "where" not in self.stop:
                self.adv()
                if self.eat("by"):
                    key = self.it_lambda(self.range_expr, False)
                    slots: tuple[tuple[str, Any], ...] = ()
                    if self.at_op(",") and self.nxt().is_word("descending"):
                        self.adv()
                        self.adv()
                        slots = (("descending", C.Lit("truth", True)),)
                    e = op_call("sort-by", [e, key], line, slots)
                else:
                    if self.at_op(",") and self.nxt().is_word("descending"):
                        raise SayError(
                            "E0130",
                            self.cur.line,
                            self.cur.col,
                            token="descending",
                            try_="write `sorted by it, descending`",
                        )
                    e = op_call("sort", [e], line)
            elif tok.is_word("grouped") and self.nxt().is_word("by") and "where" not in self.stop:
                self.adv()
                self.adv()
                e = op_call("group-by", [e, self.it_lambda(self.range_expr, False)], line)
            elif tok.is_word("joined") and self.nxt().is_word("with", "by") and "where" not in self.stop:
                self.adv()
                how = self.adv().value
                e = op_call("join" if how == "with" else "join-all", [e, self.range_expr()], line)
            elif tok.is_op("++"):
                self.adv()
                e = op_call("join", [e, self.range_expr()], line)
            else:
                return e

    def it_lambda(self, fn: Any, is_cond: bool) -> C.Lambda:
        with self.scope("lambda"):
            self.bind("it", False, self.cur.line, check=False)
            self.it_stack.append(len(self.scopes) - 1)
            try:
                stop = self.stop | {"where", "each"} if is_cond else self.stop
                body = self.with_stop(stop, fn)
            finally:
                self.it_stack.pop()
        return C.Lambda((C.Param("it"),), body)

    def cond(self) -> Any:
        left = self.c_or()
        if (self.at("or") and self.nxt().is_word("else")) or self.at_op("??"):
            line = self.adv().line
            self.eat("else")
            return op_call("default", [left, thunk(self.cond())], line)
        return left

    def c_or(self) -> Any:
        left = self.c_and()
        while (self.at("or") and not self.nxt().is_word("else")) or self.at_op("||"):
            line = self.adv().line
            left = op_call("or", [left, thunk(self.c_and())], line)
        return left

    def c_and(self) -> Any:
        left = self.c_not()
        while (self.at("and") and "and" not in self.stop) or self.at_op("&&"):
            line = self.adv().line
            left = op_call("and", [left, thunk(self.c_not())], line)
        return left

    def c_not(self) -> Any:
        if self.at("not") or self.at_op("!"):
            line = self.adv().line
            return op_call("not", [self.c_not()], line)
        return self.comparison(self.range_expr)

    # ---- P8-P12 ------------------------------------------------------------------------
    def range_expr(self) -> Any:
        a = self.additive()
        if self.at_op("..", "..<"):
            tok = self.adv()
            b = self.additive()
            slots: list[tuple[str, Any]] = []
            if tok.value == "..<":
                slots.append(("exclusive", C.Lit("truth", True)))
            if self.at("by") and "by" not in self.stop:
                self.adv()
                slots.append(("step", self.additive()))
            return op_call("range", [a, b], tok.line, tuple(slots))
        return a

    def additive(self) -> Any:
        left = self.multiplicative()
        while True:
            tok = self.cur
            if tok.is_op("+", "-"):
                fn = SYM_BINOPS[str(tok.value)]
            elif tok.is_word("plus", "minus") and tok.value not in self.stop:
                fn = WORD_BINOPS[str(tok.value)]
            else:
                return left
            self.adv()
            left = op_call(fn, [left, self.multiplicative()], tok.line)

    def multiplicative(self) -> Any:
        left = self.unary()
        while True:
            tok = self.cur
            if tok.is_op("*", "/", "//", "%"):
                self.adv()
                left = op_call(SYM_BINOPS[str(tok.value)], [left, self.unary()], tok.line)
            elif tok.is_word("times", "mod") and tok.value not in self.stop:
                self.adv()
                left = op_call(WORD_BINOPS[str(tok.value)], [left, self.unary()], tok.line)
            elif tok.is_word("divided") and self.nxt().is_word("by"):
                self.adv()
                self.adv()
                right = self.unary()
                fn = "divide"
                if self.at_op(",") and self.nxt().is_word("rounded") and self.nxt(2).is_word("down"):
                    for _ in range(3):
                        self.adv()
                    fn = "floor-divide"
                left = op_call(fn, [left, right], tok.line)
            else:
                if tok.is_op(",") and self.nxt().is_word("rounded"):
                    raise SayError(
                        "E0130",
                        tok.line,
                        tok.col,
                        token="rounded",
                        try_="`, rounded down` follows `divided by …`",
                    )
                return left

    def unary(self) -> Any:
        tok = self.cur
        if tok.is_word("negative") or tok.is_op("-"):
            self.adv()
            return op_call("negate", [self.unary()], tok.line)
        if tok.is_word("try"):
            self.adv()
            return C.Try(self.unary(), line=tok.line)
        return self.power()

    def power(self) -> Any:
        base = self.app()
        tok = self.cur
        if tok.is_op("^"):
            self.adv()
            return op_call("power", [base, self.unary()], tok.line)
        if self.at_power_words():
            for _ in range(4):
                self.adv()
            return op_call("power", [base, self.unary()], tok.line)
        return base

    def at_power_words(self) -> bool:
        return (
            self.at("to") and self.nxt().is_word("the") and self.nxt(2).is_word("power") and self.nxt(3).is_word("of")
        )

    # ---- application (P14) -------------------------------------------------------------
    def pc_arg(self) -> Any:
        e = self.unary()
        return e if "where" in self.stop else self.clauses(e)

    def app(self) -> Any:
        tok = self.cur
        if tok.kind == "NAME" and tok.value not in RESERVED_SET and not str(tok.value)[:1].isupper():
            name = str(tok.value)
            qualified = (
                name in self.modules and self.nxt().is_op(".") and not self.nxt().spaced and self.lookup(name) is None
            )
            special = name in ("problem", "evaluate", "simplify", "item") and not self.nxt().is_op("(")
            if (qualified or self.is_callee(name)) and not self.nxt().is_op("=>") and not special:
                return self.pc_call()
        e = self.postfix()
        if (
            isinstance(e, C.Name)
            and e.ref.kind == "local"
            and "with" not in self.stop
            and self.at("with")
            and self.nxt().kind == "NAME"
            and self.starts_operand(self.nxt(2), self.nxt(3))
        ):
            fields: list[tuple[str, Any]] = []
            self.named_args(fields)
            return C.RecordLit(C.TAnything(), tuple(fields), e, line=tok.line)
        return e

    def pc_call(self) -> Any:
        start = self.p
        tok = self.cur
        fn = self.callee_name()
        if self.at_op("(") and not self.cur.spaced:
            return self.postfix_ops(fn)
        lead = self.p
        args: list[Any] = []
        slots: list[tuple[str, Any]] = []
        if self.at("of") and "of" not in self.stop:
            self.adv()
            args.append(self.with_stop(self.stop | {"with"}, self.pc_arg))
        elif self.starts_operand(self.cur, self.nxt()) and not (
            self.cur.kind == "NAME" and self.cur.value in SLOT_WORDS
        ):
            args.append(self.with_stop(self.stop | {"with"}, self.pc_arg))
        arg_end = self.p
        self.slot_args(slots)
        self.named_args(slots)
        if not args and not slots:
            return self.postfix_ops(fn)
        nxt = self.cur
        if nxt.is_op("+", "-", "*", "/", "//", "%", "..", "..<") or (
            nxt.is_word("plus", "minus", "times", "divided", "mod") and nxt.value not in self.stop
        ):
            self.r6_error(start, lead, arg_end, nxt)
        return C.Call(fn, tuple(args), tuple(slots), line=tok.line)

    def r6_error(self, start: int, lead: int, arg_end: int, nxt: Tok) -> None:
        j = self.p + 1
        depth = 0
        while self.t[j].kind not in ("NEWLINE", "EOF"):
            tj = self.t[j]
            if tj.is_op("(", "[", "{"):
                depth += 1
            elif tj.is_op(")", "]", "}"):
                if depth == 0:
                    break
                depth -= 1
            elif depth == 0 and (tj.is_op(":", ",") or tj.is_word("then", "and", "or", "is")):
                break
            j += 1
        arg_start = lead + (1 if self.t[lead].is_word("of") else 0)
        callee = self.text_of(start, arg_start)
        arg = self.text_of(arg_start, arg_end)
        op = self.text_of(self.p, self.p + 1)
        rest = self.text_of(self.p + 1, j)
        r1 = f"({callee} {arg}) {op} {rest}"
        r2 = f"{callee} ({arg} {op} {rest})"
        raise SayError(
            "E0108",
            nxt.line,
            nxt.col,
            readings=[r1, r2],
            reading1=r1,
            reading2=r2,
            symbols1=r1,
            symbols2=r2,
        )

    def slot_args(self, slots: list[tuple[str, Any]]) -> None:
        while (
            self.cur.kind == "NAME"
            and self.cur.value in SLOT_WORDS
            and self.cur.value not in self.stop
            and not self.at_power_words()
        ):
            word = str(self.adv().value)
            slots.append((word, self.with_stop(self.stop | {"with"}, self.pc_arg)))

    def named_args(self, out: list[tuple[str, Any]]) -> None:
        if not (self.at("with") and self.nxt().kind == "NAME" and self.nxt().value not in RESERVED_SET):
            return
        self.adv()
        while True:
            key = self.word("an argument name")
            out.append((key, self.with_stop(self.stop | {"and"}, self.pc_arg)))
            if (
                self.at("and")
                and self.nxt().kind == "NAME"
                and self.nxt().value not in RESERVED_SET
                and self.starts_operand(self.nxt(2), self.nxt(3))
            ):
                self.adv()
                continue
            return

    def call_args(self) -> tuple[list[Any], list[tuple[str, Any]]]:
        self.expect_op("(")
        args: list[Any] = []
        slots: list[tuple[str, Any]] = []
        saved = self.stop
        self.stop = set()
        try:
            while not self.at_op(")"):
                if (
                    self.cur.kind == "NAME"
                    and self.nxt().is_op("=")
                    and (self.cur.value not in RESERVED_SET or self.cur.value in SLOT_WORDS)
                ):
                    key = str(self.adv().value)
                    self.adv()
                    slots.append((key, self.expr()))
                else:
                    if slots:
                        raise self.fail("a named argument (positional arguments come first)")
                    args.append(self.expr())
                if not self.eat_op(","):
                    break
            self.expect_op(")")
        finally:
            self.stop = saved
        return args, slots

    def postfix(self) -> Any:
        return self.postfix_ops(self.primary())

    def postfix_ops(self, e: Any) -> Any:
        while True:
            tok = self.cur
            if tok.kind == "POSS":
                self.adv()
                fld = self.word("a field name")
                e = C.Get(e, fld, self.if_any(), line=tok.line)
            elif tok.is_op(".") and not tok.spaced and self.nxt().is_word("with") and self.nxt(2).is_op("("):
                self.adv()
                self.adv()
                e = C.RecordLit(C.TAnything(), tuple(self.kwargs()), e, line=tok.line)
            elif tok.is_op(".", "?.") and not tok.spaced and self.nxt().kind == "NAME":
                self.adv()
                e = C.Get(e, self.word("a field name"), tok.value == "?.", line=tok.line)
            elif tok.is_op("[", "?[") and not tok.spaced:
                start = self.p
                self.adv()
                idx = self.with_stop(set(), self.expr)
                self.expect_op("]")
                if isinstance(idx, C.Lit) and idx.kind == "integer" and idx.value == 0:
                    j = start - 1
                    raise SayError("E0181", tok.line, tok.col, expr=self.text_of(j, start))
                e = C.Index(e, idx, tok.value == "?[" or self.if_any(), line=tok.line)
            elif tok.is_op("(") and not tok.spaced:
                args, slots = self.call_args()
                e = C.Call(e, tuple(args), tuple(slots), line=tok.line)
            elif tok.is_op("?") and not tok.spaced:
                self.adv()
                e = C.Try(e, line=tok.line)
            else:
                return e

    def kwargs(self) -> list[tuple[str, Any]]:
        self.expect_op("(")
        fields: list[tuple[str, Any]] = []
        while not self.at_op(")"):
            k = self.word("a field name")
            self.expect_op("=")
            fields.append((k, self.with_stop(set(), self.expr)))
            if not self.eat_op(","):
                break
        self.expect_op(")")
        return fields

    def if_any(self) -> bool:
        if self.at_op(",") and self.nxt().is_word("if") and self.nxt(2).is_word("any"):
            for _ in range(3):
                self.adv()
            return True
        return False

    # ---- primary (P15) -----------------------------------------------------------------
    LIT_KINDS = {"INT": "integer", "DEC": "decimal", "APPROX": "approx", "DUR": "quantity"}

    def primary(self) -> Any:
        tok = self.cur
        line = tok.line
        k = tok.kind
        if k in self.LIT_KINDS:
            self.adv()
            return C.Lit(self.LIT_KINDS[k], tok.value, line=line)
        if k == "TEXT":
            self.adv()
            return self.text_lit(tok)
        if k == "SYM":
            self.adv()
            return C.SymLit(str(tok.value), line=line)
        if k == "PATVAR":
            self.adv()
            if self.patvars is None:
                raise SayError(
                    "E0130",
                    line,
                    tok.col,
                    token=f"?{tok.value}",
                    try_="pattern variables belong in rules and `matches` patterns",
                )
            idx = self.patvars.setdefault(str(tok.value), len(self.patvars))
            return C.Name(str(tok.value), C.Ref("patvar", idx), line=line)
        if k == "NOTE":
            raise SayError("E0120", line, tok.col)
        if k == "OP":
            return self.primary_op(tok)
        if k != "NAME":
            raise self.fail("a value")
        v = str(tok.value)
        if v in ("yes", "true", "no", "false"):
            self.adv()
            return C.Lit("truth", v in ("yes", "true"), line=line)
        if v == "nothing":
            self.adv()
            return C.Lit("nothing", None, line=line)
        if v == "the":
            return self.the_phrase()
        if v in ("a", "an"):
            self.article_error(tok)
        if v == "quote":
            self.adv()
            return self.quote_body()
        if v == "item":
            self.adv()
            i = self.with_stop(self.stop | {"of"}, self.unary)
            self.expect("of")
            target = self.app()
            return C.Index(target, i, self.if_any(), line=line)
        if v == "problem" and self.nxt().kind == "NAME" and self.nxt().value not in RESERVED_SET:
            self.adv()
            kind = self.word("a problem kind")
            slots: list[tuple[str, Any]] = []
            self.named_args(slots)
            return op_call("problem", [C.SymLit(kind)], line, tuple(slots))
        if v == "from":
            return self.words_range()
        if v == "given":
            self.adv()
            names = [self.word("a parameter name")]
            while self.eat("and"):
                names.append(self.word("a parameter name"))
            self.expect_op(",")
            return self.lambda_body(names, line)
        if v == "each":
            return self.each_expr()
        if v == "evaluate":
            self.adv()
            if self.at_op("(") and not self.cur.spaced:
                args, slots = self.call_args()
                return op_call("evaluate", args, line, tuple(slots))
            e = self.pc_arg()
            slots = []
            self.named_args(slots)
            return op_call("evaluate", [e], line, tuple(slots))
        if v == "simplify":
            self.adv()
            e = self.with_stop(self.stop | {"using"}, self.pc_arg)
            self.expect("using")
            rs = self.word("a ruleset name")
            slots = []
            self.named_args(slots)
            return op_call("egraph-simplify", [e, self.name_node(rs, line)], line, tuple(slots))
        if self.nxt().is_op("=>") and not self.nolambda and v not in RESERVED_SET:
            self.adv()
            self.adv()
            return self.lambda_body([v], line)
        if v[:1].isupper():
            return self.type_name_value()
        name = self.word()
        if self.defs.get(name) == "case" and not self.lookup(name):
            fields: list[tuple[str, Any]] = []
            if self.at_op("(") and not self.cur.spaced:
                fields = self.kwargs()
            else:
                self.named_args(fields)
            return C.RecordLit(C.TName(name), tuple(fields), line=line)
        return self.name_node(name, line)

    def article_error(self, tok: Tok) -> None:
        j = self.p + 1
        while (
            self.t[j].kind not in ("NEWLINE", "EOF")
            and not self.t[j].is_word("sorted", "where", "be")
            and not self.t[j].is_op(":", ",")
        ):
            j += 1
        nxt = self.nxt()
        typeish = nxt.kind == "NAME" and (
            nxt.value in TYPEWORDS
            or str(nxt.value)[:1].isupper()
            or nxt.value in ("list", "set", "map", "text", "channel", "function")
        )
        if typeish:
            raise SayError("E0107", tok.line, tok.col, phrase=self.text_of(self.p, j), name="x", value="…")
        raise SayError("E0104", tok.line, tok.col, article=tok.value)

    def words_range(self) -> Any:
        tok = self.adv()
        a = self.with_stop(self.stop | {"to", "up", "by"}, self.additive)
        slots: list[tuple[str, Any]] = []
        if self.eat("up"):
            slots.append(("exclusive", C.Lit("truth", True)))
        self.expect("to")
        b = self.with_stop(self.stop | {"to", "by"}, self.additive)
        if self.eat("by"):
            slots.append(("step", self.additive()))
        return op_call("range", [a, b], tok.line, tuple(slots))

    def each_expr(self) -> Any:
        tok = self.adv()
        with self.scope("lambda"):
            pat, names = self.with_stop({"in"}, self.pattern, "bind")
            self.expect("in")
            source = self.range_expr()
            concurrent = False
            if self.at("at") and self.nxt().is_word("the") and self.nxt(2).is_word("same"):
                for w in ("at", "the", "same", "time"):
                    self.expect(w)
                concurrent = True
            self.expect_op(",")
            for n in names:
                self.bind(n, False, tok.line)
            body = self.cond()
        params = tuple(C.Param(n) for n in names)
        fn = "map-concurrent" if concurrent else "map"
        return op_call(fn, [source, C.Lambda(params, body)], tok.line)

    def lambda_body(self, names: list[str], line: int) -> C.Lambda:
        with self.scope("lambda"):
            for n in names:
                self.bind(n, False, line)
            body = self.with_stop(set(), self.cond)
        return C.Lambda(tuple(C.Param(n) for n in names), body, line=line)

    def text_lit(self, tok: Tok) -> Any:
        parts: list[Any] = []
        for part in tok.value:
            if isinstance(part, str):
                if parts and isinstance(parts[-1], str):
                    parts[-1] += part
                elif part:
                    parts.append(part)
                continue
            src, line, col = part
            saved = (self.t, self.p)
            self.t, self.p = lex_inline(src, line, col).tokens, 0
            try:
                e = self.with_stop(set(), self.expr)
                if self.cur.kind not in ("EOF", "NEWLINE"):
                    raise self.fail("the end of the interpolation")
            finally:
                self.t, self.p = saved
            parts.append(e)
        if all(isinstance(p_, str) for p_ in parts):
            return C.Lit("text", "".join(parts), line=tok.line)
        return C.Interp(tuple(parts), line=tok.line)

    def primary_op(self, tok: Tok) -> Any:
        v = tok.value
        line = tok.line
        if v == "(":
            if self.paren_lambda():
                self.adv()
                names: list[str] = []
                while not self.at_op(")"):
                    names.append(self.word("a parameter name"))
                    if not self.eat_op(","):
                        break
                self.expect_op(")")
                self.expect_op("=>")
                return self.lambda_body(names, line)
            self.adv()
            e = self.with_stop(set(), self.expr)
            self.expect_op(")")
            return e
        if v == "[":
            self.adv()
            items = self.with_stop(set(), self.expr_list, "]")
            return C.ListLit(tuple(items), line=line)
        if v == "{":
            return self.brace_lit(tok)
        if v == "`":
            return self.quote_body()
        if v == "~":
            self.adv()
            if not self.quote:
                raise SayError("E0901", line, tok.col, e=self.text_of(self.p, self.p + 1))
            self.quote -= 1
            try:
                inner = self.postfix()
            finally:
                self.quote += 1
            return C.Unquote(inner, line=line)
        if v == "_":
            raise SayError("E0130", line, tok.col, token="_", try_="`_` is only a pattern")
        raise self.fail("a value")

    def expr_list(self, close: str) -> list[Any]:
        items: list[Any] = []
        while not self.at_op(close):
            items.append(self.expr())
            if not self.eat_op(","):
                break
        self.expect_op(close)
        return items

    def brace_lit(self, tok: Tok) -> Any:
        self.adv()
        if self.eat_op("}"):
            return C.MapLit((), line=tok.line)
        saved = self.stop
        self.stop = set()
        try:
            first = self.expr()
            if self.eat_op(":"):
                pairs = [(first, self.expr())]
                while self.eat_op(","):
                    k_ = self.expr()
                    self.expect_op(":")
                    pairs.append((k_, self.expr()))
                self.expect_op("}")
                return C.MapLit(tuple(pairs), line=tok.line)
            items = [first]
            while self.eat_op(","):
                items.append(self.expr())
            self.expect_op("}")
        finally:
            self.stop = saved
        return C.SetLit(tuple(items), line=tok.line)

    def paren_lambda(self) -> bool:
        j = self.p + 1
        while self.t[j].kind == "NAME" or self.t[j].is_op(","):
            j += 1
        return self.t[j].is_op(")") and self.t[j + 1].is_op("=>") and not self.nolambda

    def quote_body(self) -> C.Quote:
        tok = self.cur
        self.eat_op("`")
        self.expect_op("(")
        self.quote += 1
        try:
            e = self.with_stop(set(), self.expr)
        finally:
            self.quote -= 1
        self.expect_op(")")
        return C.Quote(e, line=tok.line)

    def the_phrase(self) -> Any:
        tok = self.adv()
        line = tok.line
        if self.at("symbol") and self.nxt().kind == "NAME":
            self.adv()
            return C.SymLit(str(self.adv().value), line=line)
        if self.at("type"):
            self.adv()
            return C.TypeExpr(self.type_w(), line=line)
        fld = self.word("a field name")
        self.expect("of")
        target = self.app()
        return C.Get(target, fld, False, line=line)

    def type_name_value(self) -> Any:
        tok = self.cur
        name = str(tok.value)
        line = tok.line
        if self.nxt().is_op("[") and not self.nxt().spaced:
            return C.TypeExpr(self.type_s(), line=line)
        self.adv()
        if self.defs.get(name) in ("record", "case") or name == "Pair":
            fields: list[tuple[str, Any]] = []
            if self.at_op("(") and not self.cur.spaced:
                fields = self.kwargs()
            else:
                self.named_args(fields)
            return C.RecordLit(C.TName(name), tuple(fields), line=line)
        if name in SYM_TYPES or self.defs.get(name) == "variant":
            return C.TypeExpr(C.TName(SYM_TYPES.get(name, name)), line=line)
        return C.Name(name, self.ref_for(name), line=line)

    # ---- patterns (spec 03 section 5.6, ebnf section 10) ---------------------------------
    def pattern(self, mode: str) -> tuple[Any, list[str]]:
        names: list[str] = []
        line = self.cur.line
        alts = [self.single(mode, names)]
        while self.at("or") and "or" not in self.stop:
            self.adv()
            more: list[str] = []
            alts.append(self.single(mode, more))
            if set(more) != set(names):
                raise SayError("E0904", line, names=", ".join(sorted(set(more) ^ set(names))))
        if len(alts) == 1:
            return alts[0], names
        return C.PAlt(tuple(alts)), names

    def lit_token(self) -> C.Lit | None:
        tok = self.cur
        if tok.kind in self.LIT_KINDS:
            self.adv()
            return C.Lit(self.LIT_KINDS[tok.kind], tok.value)
        if tok.kind == "TEXT" and all(isinstance(p_, str) for p_ in tok.value):
            self.adv()
            return C.Lit("text", "".join(tok.value))
        if tok.is_word("yes", "true", "no", "false"):
            self.adv()
            return C.Lit("truth", tok.value in ("yes", "true"))
        if tok.is_word("nothing"):
            self.adv()
            return C.Lit("nothing", None)
        if tok.is_op("-") and self.nxt().kind in ("INT", "DEC"):
            self.adv()
            n = self.adv()
            return C.Lit("integer" if n.kind == "INT" else "decimal", -n.value)
        return None

    def single(self, mode: str, names: list[str]) -> Any:
        tok = self.cur
        if mode == "bind" and (tok.kind == "POSS" or (tok.kind == "NAME" and tok.value in RESERVED_SET)):
            raise SayError("E0109", tok.line, tok.col, word=str(tok.value))
        if tok.kind == "PATVAR":
            self.adv()
            ptype = None
            if self.at_op("(") and self.cur.spaced:
                self.adv()
                ptype = self.type_w()
                self.expect_op(")")
            elif self.at_op(":") and not self.nxt().kind == "NEWLINE":
                self.adv()
                ptype = self.type_s()
            names.append(str(tok.value))
            return C.PBind(str(tok.value), ptype)
        if tok.is_word("anything") or tok.is_op("_"):
            self.adv()
            return C.PWild()
        if tok.is_word("from") and mode != "bind":
            self.adv()
            lo = self.lit_token()
            up = self.eat("up")
            self.expect("to")
            hi = self.lit_token()
            return C.PRange(C.PLit(lo), C.PLit(hi), not up)
        lit = self.lit_token()
        if lit is not None:
            if self.at_op("..", "..<"):
                inclusive = self.adv().value == ".."
                return C.PRange(C.PLit(lit), C.PLit(self.lit_token()), inclusive)
            return C.PLit(lit)
        if tok.is_op("["):
            return self.list_pattern(mode, names)
        if tok.is_word("quote") or tok.is_op("`"):
            self.eat("quote")
            q = self.quoted_pattern(self.quote_body)
            inner = q.expr.expr if isinstance(q.expr, C.Quote) else q.expr
            return C.PQuote(inner)
        if tok.is_op("("):
            self.adv()
            inner, n2 = self.pattern(mode)
            names += n2
            self.expect_op(")")
            return inner
        if tok.kind == "NAME" and str(tok.value)[:1].isupper():
            self.adv()
            fields, open_ = self.field_pats(mode, names)
            return C.PRecord(C.TName(str(tok.value)), fields, open_)
        if tok.kind == "NAME":
            name = self.word("a pattern")
            if mode == "bind":
                names.append(name)
                return C.PBind(name)
            fields, open_ = self.field_pats(mode, names)
            return C.PCase(name, fields, open_)
        raise self.fail("a pattern")

    def list_pattern(self, mode: str, names: list[str]) -> C.PList:
        self.adv()
        prefix: list[Any] = []
        rest = None
        while not self.at_op("]"):
            if self.eat_op("..."):
                rest = self.single(mode, names)
                break
            prefix.append(self.single(mode, names))
            if not self.eat_op(","):
                break
        self.expect_op("]")
        return C.PList(tuple(prefix), rest)

    def field_pats(self, mode: str, names: list[str]) -> tuple[tuple[tuple[str, Any], ...], bool]:
        fields: list[tuple[str, Any]] = []
        open_ = False
        if self.at("with"):
            self.adv()
            while True:
                fname = self.word("a field name")
                nxt = self.cur
                if (
                    nxt.kind in ("PATVAR", "INT", "DEC", "TEXT", "APPROX", "DUR")
                    or nxt.is_op("[", "_", "(", "-")
                    or nxt.is_word("anything", "yes", "no", "nothing", "true", "false", "quote")
                    or (nxt.kind == "NAME" and str(nxt.value)[:1].isupper())
                ):
                    fields.append((fname, self.single(mode, names)))
                else:
                    names.append(fname)
                    fields.append((fname, C.PBind(fname)))
                if self.at_op(",") and self.nxt().is_word("and") and self.nxt(2).is_word("more"):
                    for _ in range(3):
                        self.adv()
                    open_ = True
                    break
                if (
                    (self.at("and") or self.at_op(","))
                    and self.nxt().kind == "NAME"
                    and self.nxt().value not in RESERVED_SET
                ):
                    self.adv()
                    continue
                break
        elif self.at_op("(") and not self.cur.spaced:
            self.adv()
            while not self.at_op(")"):
                if self.eat_op("..."):
                    open_ = True
                    break
                fname = self.word("a field name")
                self.expect_op("=")
                fields.append((fname, self.single(mode, names)))
                if not self.eat_op(","):
                    break
            self.expect_op(")")
        return tuple(fields), open_

    # ---- types (ebnf section 9, rule R1) -----------------------------------------------
    def type_any(self) -> Any:
        if (self.cur.kind == "NAME" and str(self.cur.value)[:1].isupper()) or self.at_op("("):
            return self.type_s()
        return self.type_w()

    def type_w(self) -> Any:
        types = [self.type_w1()]
        while self.at("or") and not self.nxt().is_word("else"):
            self.adv()
            types.append(self.type_w1())
        return make_union(types)

    def type_w1(self) -> Any:
        self.eat("a", "an")
        tok = self.cur
        if tok.kind != "NAME":
            raise self.fail("a type")
        v = str(tok.value)
        if v == "anything":
            self.adv()
            return C.TAnything()
        if v in ("nothing", "text") or v in TYPEWORDS:
            self.adv()
            return C.TName(v)
        if v in ("list", "set", "channel"):
            self.adv()
            self.expect("of")
            return C.TApply(v, (self.plural_w(),))
        if v == "map":
            self.adv()
            self.expect("from")
            k_ = self.plural_w()
            self.expect("to")
            return C.TApply("map", (k_, self.plural_w()))
        if v == "function":
            return self.func_type_w()
        if v in ("money", "quantity"):
            raise SayError(
                "E1013",
                tok.line,
                tok.col,
                construct=f"the `{v}` type",
                profile="v0.1",
                version="v0",
            )
        if v[:1].isupper():
            self.adv()
            return C.TName(v)
        raise self.fail("a type")

    def func_type_w(self) -> C.TFunc:
        self.adv()
        self.expect("from")
        params = [self.type_w1()]
        while self.eat("and"):
            params.append(self.type_w1())
        self.expect("to")
        result = self.type_w1()
        effects: tuple[C.EffItem, ...] = ()
        if self.at_op(",") and self.nxt().is_word("needs"):
            self.adv()
            self.adv()
            effects = self.effect_row()
        return C.TFunc(tuple(params), result, effects)

    def plural_w(self) -> Any:
        tok = self.cur
        v = str(tok.value)
        if tok.kind != "NAME":
            raise self.fail("a plural type")
        if v in ("text", "anything"):
            self.adv()
            return C.TAnything() if v == "anything" else C.TName("text")
        if v in PLURALS:
            self.adv()
            base = PLURALS[v]
            if base in ("list", "set", "channel") and self.eat("of"):
                return C.TApply(base, (self.plural_w(),))
            if base == "map" and self.eat("from"):
                k_ = self.plural_w()
                self.expect("to")
                return C.TApply("map", (k_, self.plural_w()))
            return C.TName(base)
        user = {pl: n for n, pl in self.plural_names.items()}.get(v)
        if user:
            self.adv()
            return C.TName(user)
        if v[:1].isupper():
            self.adv()
            return C.TName(v)
        if v in TYPEWORDS or v in ("list", "set", "map"):
            raise SayError("E0130", tok.line, tok.col, token=v, try_=f"use the plural, like `{plural_of(v)}`")
        raise self.fail("a plural type")

    def type_s(self) -> Any:
        types = [self.type_s1()]
        while self.eat_op("|"):
            types.append(self.type_s1())
        return make_union(types)

    def type_s1(self) -> Any:
        tok = self.cur
        if self.at_op("("):
            self.adv()
            params: list[Any] = []
            while not self.at_op(")"):
                params.append(self.type_s())
                if not self.eat_op(","):
                    break
            self.expect_op(")")
            self.expect_op("->")
            result = self.type_s()
            effects: tuple[C.EffItem, ...] = ()
            if self.eat("needs"):
                effects = self.effect_row()
            return C.TFunc(tuple(params), result, effects)
        if tok.kind != "NAME" or not str(tok.value)[:1].isupper():
            raise self.fail("a type name")
        v = str(self.adv().value)
        t: Any
        if v in SYM_HEADS:
            self.expect_op("[")
            args = [self.type_s()]
            while self.eat_op(","):
                args.append(self.type_s())
            self.expect_op("]")
            t = C.TApply(SYM_HEADS[v], tuple(args))
        elif v == "Anything":
            t = C.TAnything()
        elif v in ("Money", "Quantity"):
            raise SayError(
                "E1013",
                tok.line,
                tok.col,
                construct=f"the `{v}` type",
                profile="v0.1",
                version="v0",
            )
        else:
            t = C.TName(SYM_TYPES.get(v, v))
        if self.at_op("?") and not self.cur.spaced:
            self.adv()
            t = C.TOptional(t)
        return t


# ---- module-level helpers --------------------------------------------------------------
def make_union(types: list[Any]) -> Any:
    """`a T or nothing` is optional; unions are flattened, deduplicated and ordered
    (spec 04 section 2.4; ordering by SCS-1 bytes is applied by `scs.py`)."""
    flat: list[Any] = []
    for t in types:
        while isinstance(t, C.TOptional):
            flat.append(C.TName("nothing"))
            t = t.type
        flat.extend(t.types if isinstance(t, C.TUnion) else [t])
    is_nothing = [isinstance(t, C.TName) and t.ref == "nothing" for t in flat]
    rest = [t for t, n in zip(flat, is_nothing) if not n]
    uniq: list[Any] = []
    for t in sorted(rest, key=repr):
        if t not in uniq:
            uniq.append(t)
    if not uniq:
        return C.TName("nothing")
    core_t = uniq[0] if len(uniq) == 1 else C.TUnion(tuple(uniq))
    return C.TOptional(core_t) if any(is_nothing) else core_t


def tvars(t: Any, names: set[str]) -> Any:
    if t is None or not names:
        return t
    if isinstance(t, C.TName):
        return C.TVar(t.ref) if t.ref in names else t
    if isinstance(t, C.TApply):
        return C.TApply(t.head, tuple(tvars(a, names) for a in t.args))
    if isinstance(t, C.TOptional):
        return C.TOptional(tvars(t.type, names))
    if isinstance(t, C.TUnion):
        return C.TUnion(tuple(tvars(a, names) for a in t.types))
    if isinstance(t, C.TFunc):
        return C.TFunc(tuple(tvars(a, names) for a in t.params), tvars(t.result, names), t.effects, t.fails)
    return t


def irrefutable(p: Any) -> bool:
    if isinstance(p, (C.PBind, C.PWild)):
        return True
    if isinstance(p, C.PRecord):
        return all(irrefutable(f) for _, f in p.fields)
    return False


def bind_refs(p: Any, refs: dict[str, C.Ref]) -> Any:
    if isinstance(p, C.PBind):
        return replace(p, ref=refs.get(p.name))
    if isinstance(p, (C.PRecord, C.PCase)):
        return replace(p, fields=tuple((k, bind_refs(v, refs)) for k, v in p.fields))
    if isinstance(p, C.PList):
        rest = bind_refs(p.rest, refs) if p.rest is not None else None
        return C.PList(tuple(bind_refs(x, refs) for x in p.prefix), rest)
    if isinstance(p, C.PAlt):
        return C.PAlt(tuple(bind_refs(x, refs) for x in p.alts))
    return p


def check_of(subject: Any, line: int) -> C.Check:
    if is_op(subject, "equal"):
        return C.Check(None, subject.args[0], "equals", subject.args[1], None, line=line)
    if is_op(subject, "match"):
        return C.Check(None, subject.args[0], "matches", subject.args[1], None, line=line)
    if isinstance(subject, C.TypeTest):
        return C.Check(None, subject.value, "is", C.TypeExpr(subject.type), None, line=line)
    return C.Check(None, subject, "holds", None, None, line=line)


def transform(n: Any, fn: Any) -> Any:
    """Rebuild a core tree bottom-up, applying `fn` to every node and structure."""
    if isinstance(n, tuple):
        return tuple(transform(x, fn) for x in n)
    if isinstance(n, C.Node) or isinstance(n, C.STRUCTS):
        changes = {}
        for f in fields(n):
            v = getattr(n, f.name)
            nv = transform(v, fn)
            if nv is not v:
                changes[f.name] = nv
        if changes:
            n = replace(n, **changes)
        return fn(n)
    return n


def finish(mod: C.Module, sigs: dict[str, Any]) -> C.Module:
    """Normalise slot order (callee declaration order, else code point order) and record
    field order (declaration order); spec 04 section 2.3 (`Call`, `RecordLit`)."""
    table: dict[str, list[str]] = {}
    for name, sig in list(HOST_SIGS.items()) + list(PRELUDE_SIGS.items()) + list(sigs.items()):
        table[name] = [lead if lead in SLOT_WORDS else pname for lead, pname, _ in sig if lead not in (None, "of")]
    rec: dict[str, list[str]] = {}
    for d in mod.body:
        if isinstance(d, C.RecordDef):
            rec[d.name] = [f.name for f in d.fields]
        elif isinstance(d, C.VariantDef):
            for c in d.cases:
                rec[c.name] = [f.name for f in c.fields]

    def order(pairs: tuple[tuple[str, Any], ...], decl: list[str] | None) -> tuple[tuple[str, Any], ...]:
        if decl is None:
            return tuple(sorted(pairs, key=lambda kv: kv[0]))
        pos = {k: i for i, k in enumerate(decl)}
        return tuple(sorted(pairs, key=lambda kv: (pos.get(kv[0], len(pos)), kv[0])))

    def fix(n: Any) -> Any:
        if isinstance(n, C.Call) and n.slots:
            decl = None
            if isinstance(n.fn, C.Name) and n.fn.ref.kind in ("def", "builtin"):
                decl = table.get(n.fn.name)
            return replace(n, slots=order(n.slots, decl))
        if isinstance(n, (C.RecordLit, C.PRecord)) and isinstance(n.type, C.TName):
            return replace(n, fields=order(n.fields, rec.get(n.type.ref)))
        if isinstance(n, C.PCase):
            return replace(n, fields=order(n.fields, rec.get(n.case)))
        return n

    out: C.Module = transform(mod, fix)
    return out


def parse(text: str, file: str = "", sink: Sink | None = None, name: str = "main") -> C.Module:
    """Parse and lower one module (spec 03, spec 04 section 3)."""
    return Parser(lex(text), file, sink).parse_module(name)
