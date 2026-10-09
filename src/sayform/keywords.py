"""Reserved and contextual words (spec/02-lexical.md section 5 and 6).

Edition 0 budgets: exactly 63 reserved words and 89 contextual words (Law 5).
`tools/check_spec_sync.py` checks these tuples against the spec tables.
"""

from __future__ import annotations

#: spec 02 section 5, in table order (63).
RESERVED: tuple[str, ...] = (
    "let", "be", "set", "to", "change", "var",
    "give", "return", "giving", "given", "needs", "may", "with", "try",
    "if", "otherwise", "else", "match", "when", "for", "each", "in",
    "repeat", "while", "stop", "skip",
    "and", "or", "not", "is", "equals", "contains",
    "the", "a", "an", "of", "'s",
    "by", "where", "then", "from",
    "quote", "evaluate", "rewrite", "as", "simplify", "using", "ruleset",
    "module", "use", "dialect", "effect",
    "together", "within",
    "has", "role",
    "yes", "no", "nothing", "true", "false",
    "note", "check",
)  # fmt: skip

#: spec 02 section 6, in table order (89).
CONTEXTUAL: tuple[str, ...] = (
    "back", "fail", "times", "up",
    "less", "greater", "than", "at", "least", "most", "equal", "same", "between",
    "equivalent", "one", "exclusive", "above", "below", "descending",
    "rounded", "down", "changeable", "default", "plural", "limited", "read", "only",
    "edition", "plus", "minus", "divided", "mod", "negative", "power",
    "joined", "sorted", "grouped", "matches", "item", "problem", "approx",
    "all", "first", "all-of", "first-of", "time", "received", "any", "that", "fails",
    "example", "gives", "it", "anything", "more", "symbol", "type",
    "def", "elif", "break", "continue", "record", "variant", "case", "into",
    "millisecond", "milliseconds", "second", "seconds", "minute", "minutes",
    "ms", "s", "min",
    "operator", "operands", "binds", "like", "left", "right", "means",
    "plays", "Self", "python", "c", "wasm", "library", "explained", "add",
)  # fmt: skip

RESERVED_SET = frozenset(RESERVED)
CONTEXTUAL_SET = frozenset(CONTEXTUAL)

#: The 9 built-in effects (spec 09 section 1).
EFFECTS: tuple[str, ...] = (
    "console", "files", "network", "clock", "random",
    "environment", "processes", "foreign", "tasks",
)  # fmt: skip

#: Slot words (spec 03 section 5.2, C-06).
SLOT_WORDS = frozenset({"to", "from", "by", "into", "for"})
LEADS = frozenset({"of", "to", "from", "by", "into", "for", "with"})

TIME_UNITS: dict[str, str] = {
    "millisecond": "ms", "milliseconds": "ms", "ms": "ms",
    "second": "s", "seconds": "s", "s": "s",
    "minute": "min", "minutes": "min", "min": "min",
}  # fmt: skip
