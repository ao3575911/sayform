# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- M6: standard library rows: `LIB-<name>` tests for the core, console, number, text and
  collection host primitives (normal cases and their panics), top-level check execution
  (`run_checks`, captured console, virtual clock, seeded random), and `prelude/prelude.test.say`
  exercising all 21 Sayform prelude functions (`LIB-PRELUDE-SAY`, G-14). Calls that lower
  slot arguments positionally (`join_all(xs, ", ")`) bind them to slot parameters in order.
- M5: effects and capabilities: static effect checks before a run (`checker.py`, SAY-E0501,
  SAY-E0601, module header coverage, top-level `let`), capability context with narrowing on
  calls and `with … limited to …[, read only]` (SAY-E0504 on widening), revocation at block exit
  (SAY-E0502 for escaped closures), host policy (`say run --deny`, `network` refused, SAY-E0506
  exit 4), `files.read-text`/`files.write-text` confined to the narrowed subtree, `clock.now`
  (virtual when seeded) and seeded `random.random-integer`, the `CapabilityBacking` hook
  (non-ok answer → problem `capability-revoked`). Tests `CAP-01`…`CAP-12`, `CAP-16`, `CAP-17`, `CAP-20`.
- M4: values and evaluator (`values.py`, `evaluator.py`, `builtins.py`): exact numbers
  (Integer/Decimal/Rational normalisation, scale rules, `//`, `mod`, `^`), approx contagion,
  text by grapheme clusters, records/variants with defaults, invariants and copy-with,
  1-based collections, generator-based evaluation, closures by reference, patterns,
  problems/`try`/`or else`, panics with 5-part output, multiple dispatch with most-specific
  choice and SAY-E0402, call depth limit. `say run` with exit codes 0/1/2/4/70.
  The 21-function prelude in Sayform (`prelude/prelude.say`), shipped in the wheel.
  Tests: `NUM`, `TXT`, `REC`, `COL`, `SEM`, `PAT`, `ERRV`, `DSP` rows in `tests/test_semantics.py`.
- M3: canonical printers for both surfaces (`src/sayform/printer.py`), SCS-1 canonical
  serialisation and BLAKE3 core hashes with SCC handling (`src/sayform/scs.py`),
  `say fmt [--words|--symbols] [--check]`, `say core [--json]`, `say hash [--defs]`.
  Tests: round-trip laws L1-L5 on generated core trees (Hypothesis; 200 examples per PR,
  `SAYFORM_RT_EXAMPLES` for nightly), RT-MUT, corpus round trips, `LOW` rows,
  `HASH-01`...`HASH-12` (byte vectors in `conformance/hash/vectors.toml`), G-01 prints.

### Spec gaps (decided provisionally, flagged)
- `add 1 to n` / `n += 1` on a number adds (12-stdlib defines `added` only for collections).
- `display` of a Symbol is `'name`; of a function value `function NAME`.
- `main` returning a problem prints `problem[KIND]` with what/why/try (no registry code exists).
- `empty-set` is provided by the host: no Sayform expression builds an empty set.
- Grapheme clusters follow UAX #29 rules over Python's `unicodedata` tables (15.0 on 3.12, 15.1 on 3.13).
- `Nothing` joins `Set` as an exemption from SAY-E0103 (issue #3).
- SCS-1: interpolation text parts and quantity numbers carry a one-byte kind marker.
- Words-surface parameter, result and field types also accept a symbols type, so types
  the words type grammar cannot spell (e.g. `List[Number | Text]`) still print losslessly.
- M2: hand-written parser for both surfaces with direct lowering to the core
  (`src/sayform/parser.py`), disambiguation rules R1-R20, SAY-E0108 with both readings,
  `GRM-01`...`GRM-30` tests and the parser-level parts of `LEX-20`/`LEX-21`.
- `tests/test_ebnf.py`: `spec/03-grammar.ebnf` is loaded with Lark to keep it well formed.
- ADR 0001 (`docs/adr/0001-hand-written-parser.md`): why the parser is hand-written.
- M0: project scaffold, Apache-2.0 licence, spec 0.1-lite imported into `spec/`,
  CI (lint, types, tests, budgets, spec sync, wheel smoke test), `say --version`,
  `tools/check_budgets.py`, `tools/check_spec_sync.py`, generated error registry.
- M1: lexer for spec/02-lexical.md (UTF-8, BOM, line ends, indentation, words,
  numbers, text with escapes and interpolation, durations, comments, notes, operators,
  Unicode aliases) with lexer-level `LEX-01`…`LEX-24` tests.
