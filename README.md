# Sayform

Sayform is a small programming language that reads like English and prints as symbols.
Every program has two surfaces, words and symbols, that lower to one canonical core.
Effects are declared with `needs` and granted by the host; nothing has ambient authority.
Expressions are data, so rewriting and simplifying code is ordinary code. This repository
is the reference interpreter for [spec 0.1-lite](spec/00-README.md) (edition 0), written in
Python 3.12+.

The language is defined by [`spec/`](spec/00-README.md). Where code and spec disagree, the
spec wins and the gap is filed as a `spec-gap` issue.

## Status

Work ships milestone by milestone (build plan, section 6). Checked items are merged on `main`.

| M | Delivers | State |
|---|---|---|
| M0 | Scaffold, licence, spec import, CI, `say --version`, budget and spec-sync checks | done |
| M1 | Lexer | done (lexer-level `LEX-*`; fmt and parser parts follow in M2/M3) |
| M2 | Parser for both surfaces, disambiguation R1–R20 | not started |
| M3 | Core AST, lowering, printers, `say fmt`, `say core`, SCS-1, `say hash` | not started |
| M4 | Values and evaluator | not started |
| M5 | Effects, capability context, host policy | not started |
| M6 | 53 host primitives and the 21-function prelude | not started |
| M7 | Symbolic: quote, `evaluate`, rulesets, `simplify` | not started |
| M8 | Concurrency: `together`, `all of`, `first of`, `within`, channels | not started |
| M9 | Tooling: `say run/check/test/explain`, REPL, diagnostics | not started |
| M10 | Modules and the `strict` dialect | not started |
| M11 | Golden programs G-01 to G-14, README demo, release 0.0.1 | not started |

Until M11 the 60-second demo below is not runnable; the commands that exist today are:

```sh
pipx install git+https://github.com/ao3575911/sayform
say --version
```

## Budgets

The language has hard size limits (spec 01 section 5): 63 reserved words, 89 contextual
words, 44 core nodes (40 in v0), 74 builtins, 96 error codes, two runtime dependencies
(`lark`, `blake3`) and at most 8,000 interpreter lines. `python tools/check_budgets.py`
enforces them in CI, and `python tools/check_spec_sync.py` checks that keyword lists and
error codes match the spec tables.

## Development

```sh
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
ruff check . && ruff format --check . && mypy --strict src/ && pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Prior art

Sayform borrows from these projects and papers (details in
[spec/16-prior-art.md](spec/16-prior-art.md)):

- [Racket `#lang`](https://github.com/racket/racket) · <https://docs.racket-lang.org/guide/hash-languages.html>
- [egglog](https://github.com/egraphs-good/egglog) · <https://github.com/egraphs-good/egglog-python> · <https://egglog-python.readthedocs.io/>
- [egg](https://github.com/egraphs-good/egg)
- [Unison](https://github.com/unisonweb/unison) · <https://www.unison-lang.org/docs/the-big-idea/>
- [Koka](https://github.com/koka-lang/koka) · <https://koka-lang.github.io/koka/doc/book.html>
- [Roc](https://github.com/roc-lang/roc) · <https://www.roc-lang.org/platforms>
- [Austral](https://github.com/austral/austral) · <https://austral-lang.org/spec/spec.html>
- [Deno permissions](https://docs.deno.com/runtime/fundamentals/security/) · <https://github.com/denoland/deno>
- [Hedy](https://github.com/hedyorg/hedy) · <https://hedy.org/research/Hedy_A_Gradual_Language_for_Programming_Education_2020.pdf>
- [Elm error messages](https://elm-lang.org/news/compiler-errors-for-humans) · <https://github.com/elm/compiler>
- [Gleam](https://gleam.run/) · <https://github.com/gleam-lang/gleam>
- [Trio](https://trio.readthedocs.io/en/stable/reference-core.html) · <https://github.com/python-trio/trio>
- [Kotlin coroutines](https://kotlinlang.org/docs/coroutines-basics.html)
- [Java StructuredTaskScope](https://openjdk.org/jeps/525)
- [Python TaskGroup / PEP 654](https://peps.python.org/pep-0654/)
- [Go channels](https://go.dev/ref/spec)
- [Lua indexing](https://www.lua.org/pil/11.1.html) · <https://github.com/lua/lua>
- [Julia](https://docs.julialang.org/en/v1/manual/noteworthy-differences/) · <https://docs.julialang.org/en/v1/manual/methods/> · <https://github.com/JuliaLang/julia>
- [Dijkstra EWD 831](https://www.cs.utexas.edu/~EWD/transcriptions/EWD08xx/EWD831.html)
- [Wolfram Language rules](https://reference.wolfram.com/language/tutorial/PatternsAndTransformationRules.html)
- [Lisp homoiconicity](https://www-formal.stanford.edu/jmc/recursive.pdf) · <https://small.r7rs.org/attachment/r7rs.pdf>
- [Inform 7](https://github.com/ganelson/inform) · <https://ganelson.github.io/inform-website/>
- [AppleScript (lesson)](https://www.cs.utexas.edu/~wcook/Drafts/2006/ashopl.pdf)
- [Swift SE-0304](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0304-structured-concurrency.md)
- [Mojo](https://github.com/modular/modular)
- [OpenXTalk-Beyond (HyperTalk lineage)](https://github.com/SethMorrowSoftware/OpenXTalk-Beyond)
- [plain-lang, englang (recent English-like languages)](https://github.com/StudioPlatforms/plain-lang) · <https://github.com/Prasundas99/englang>
- [Nim](https://github.com/nim-lang/Nim)
- [SymPy](https://github.com/sympy/sympy)
- [Python `doctest`, `fractions`, `decimal`](https://docs.python.org/3/library/doctest.html) · <https://docs.python.org/3/library/fractions.html> · <https://docs.python.org/3/library/decimal.html>
- [F# units of measure](https://learn.microsoft.com/en-us/dotnet/fsharp/language-reference/units-of-measure)
- [Rust orphan rule and editions](https://doc.rust-lang.org/reference/items/implementations.html) · <https://doc.rust-lang.org/edition-guide/editions/index.html>
- [BLAKE3](https://github.com/BLAKE3-team/BLAKE3) · <https://c2sp.org/BLAKE3> · <https://datatracker.ietf.org/doc/html/draft-aumasson-blake3>
- [Lark](https://github.com/lark-parser/lark) · <https://lark-parser.readthedocs.io/en/stable/>
- [Hypothesis](https://github.com/HypothesisWorks/hypothesis) · <https://hypothesis.readthedocs.io/en/latest/>
- [Black](https://black.readthedocs.io/en/stable/the_black_code_style/current_style.html) · <https://github.com/psf/black>
- [Unicode UAX #15, #29, #31, UTS #39](https://www.unicode.org/reports/tr15/) · <https://www.unicode.org/reports/tr29/> · <https://www.unicode.org/reports/tr31/> · <https://www.unicode.org/reports/tr39/> · <https://www.unicode.org/versions/Unicode15.1.0/>
- [atHome (Adam's spine)](https://github.com/ao3575911/atHome)

## Licence

Apache-2.0; see [LICENSE](LICENSE) and [NOTICE](NOTICE). The optional atHome capability
adapter is AGPL-3.0 and lives in its own repository; no atHome code is included or
imported here.
