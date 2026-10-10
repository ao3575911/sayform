# ADR 0001: hand-written parser; Lark validates the grammar file

- Status: accepted (decided by the maintainer, 10 Oct 2026)
- Context: build plan section 3 names `lark` (with its `Indenter`) as the parser and
  section 5 describes `parser.py` as "Lark -> surface tree".

## Context
The Sayform grammar (spec/03-grammar.md, spec/03-grammar.ebnf) depends on context in ways
a context-free parser generator does not express directly:

- contextual words are keywords only in certain slots (spec/02-lexical.md section 6);
- rules R1-R20 decide between readings using what a name resolves to (R6 prefix calls,
  R10 implicit `it`, R11 `with` after a callee, R12 `and` in named arguments);
- R5 requires reporting SAY-E0108 with both readings instead of picking one.

With Lark these rules would run as a second pass over an ambiguous Earley forest or a
permissive surface tree, which roughly doubles the parsing code and makes diagnostics
harder to point at the right token.

## Decision
- `src/sayform/parser.py` is a hand-written recursive-descent parser over the tokens from
  `lexer.py`. It resolves names as it binds them and lowers directly to the core
  (spec/04-core-ast.md section 3).
- `lark` stays a runtime dependency (budget: 2) and is used by `tests/test_ebnf.py` to load
  `spec/03-grammar.ebnf` as a Lark grammar, so the normative EBNF stays well formed: every
  referenced rule is defined and the grammar loads.
- The conformance tests `GRM-01`...`GRM-30` check the parser against the prose rules.

## Consequences
- One pass from tokens to core; diagnostics carry exact token positions.
- The EBNF is still checked mechanically, but the parser is not generated from it, so the
  GRM tests and the round-trip property tests are the guard against drift.
