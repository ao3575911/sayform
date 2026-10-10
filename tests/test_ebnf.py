"""Validate spec/03-grammar.ebnf with Lark (docs/adr/0001-hand-written-parser.md).

The reference parser is hand-written; Lark is used here only to check that the normative
EBNF is well formed: it converts to a Lark grammar in which every referenced rule is
defined and every rule is reachable from `file`.
"""

from __future__ import annotations

import re
from pathlib import Path

from lark import Lark

EBNF = Path(__file__).resolve().parents[1] / "spec" / "03-grammar.ebnf"


def strip_comments(text: str) -> str:
    """Remove (* ... *) comments, which may nest; quoted terminals are kept."""
    out: list[str] = []
    depth, i = 0, 0
    while i < len(text):
        if text.startswith('"', i) and depth == 0:
            j = text.index('"', i + 1)
            out.append(text[i : j + 1])
            i = j + 1
        elif text.startswith("(*", i):
            depth += 1
            i += 2
        elif text.startswith("*)", i) and depth:
            depth -= 1
            i += 2
        else:
            if depth == 0:
                out.append(text[i])
            i += 1
    return "".join(out)


def to_lark(text: str) -> tuple[str, set[str], set[str]]:
    body = strip_comments(text)
    rules: dict[str, str] = {}
    for m in re.finditer(r"([a-z_][a-z0-9_]*)\s*=(.*?);(?=\s*(?:[a-z_][a-z0-9_]*\s*=|$))", body, re.S):
        rules[m.group(1)] = " ".join(m.group(2).split())
    tokens: set[str] = set()
    out = []
    for name, rhs in rules.items():
        rhs = rhs.replace("{", "(").replace("}", ")*")
        tokens |= set(re.findall(r"\b[A-Z][A-Z0-9_]+\b", rhs))
        out.append(f"{name}: {rhs}")
    out += [f"%declare {t}" for t in sorted(tokens)]
    return "\n".join(out) + "\n", set(rules), tokens


def test_ebnf_loads_in_lark() -> None:
    grammar, rules, _ = to_lark(EBNF.read_text(encoding="utf-8"))
    lk = Lark(grammar, start="file", parser="earley", lexer="basic")
    defined = {r.origin.name for r in lk.rules}
    assert {"file", "expr", "pattern", "type_w", "type_s"} <= {str(d) for d in defined}


def test_every_rule_referenced_is_defined() -> None:
    _, rules, _ = to_lark(EBNF.read_text(encoding="utf-8"))
    body = strip_comments(EBNF.read_text(encoding="utf-8"))
    used = set(re.findall(r"(?<![\"\w])([a-z_][a-z0-9_]*)(?![\"\w])", re.sub(r'"[^"]*"', " ", body)))
    assert used <= rules
