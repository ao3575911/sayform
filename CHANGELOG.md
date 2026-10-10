# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- M3: canonical printers for both surfaces (`src/sayform/printer.py`), SCS-1 canonical
  serialisation and BLAKE3 core hashes with SCC handling (`src/sayform/scs.py`),
  `say fmt [--words|--symbols] [--check]`, `say core [--json]`, `say hash [--defs]`.
  Tests: round-trip laws L1-L5 on generated core trees (Hypothesis; 200 examples per PR,
  `SAYFORM_RT_EXAMPLES` for nightly), RT-MUT, corpus round trips, `LOW` rows,
  `HASH-01`...`HASH-12` (byte vectors in `conformance/hash/vectors.toml`), G-01 prints.

### Spec gaps (decided provisionally, flagged)
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
