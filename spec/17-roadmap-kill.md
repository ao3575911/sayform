# 17 · Roadmap and kill criteria
Spec `0.1-lite`. Release numbering: roadmap phase **v0 → release `0.0.x`**, phase **v0.1 → `0.1.x`**, phase **v1 → `1.0.0`** together with `SAY-SPEC-1` and edition 1.

## 1. v0 — reference interpreter (target: a few focused weeks; OPINION)
**Scope:** everything in the v0 profile.
- Python 3.12+ reference interpreter: Lark parser (with `Indenter`), frozen-dataclass core (40 v0 nodes + 18 sub-nodes), lowering, words and symbols printers, formatter, `explain`, tree-walking generator-based evaluator, deterministic single-threaded scheduler, SCS-1 + BLAKE3 hashing.
- Exact numbers (`fractions`, `decimal` from the Python standard library), text with Unicode 15.1.0 grapheme tables generated into the repository, persistent collections (tuples/dicts acceptable).
- Capabilities `console`, `files`, `clock`, `random`, `tasks`; host policy; `strict` dialect.
- Symbolic core with the pure rewrite fallback.
- 74 builtins (21 in `.say`), CLI `run fmt explain check test hash core` + REPL.
- Conformance suite of [15-conformance.md](15-conformance.md) (v0 items), round-trip properties at 200/PR.
**Exit:** all v0 conformance tests pass; release `0.0.1`.

## 2. v0.1 — about a month after v0 (OPINION)
- Roles and `plays`, user `effect` declarations, `compare`/`Order`, `explained as`.
- User dialects (`operator` declarations, hygiene, conflicts) and the `money`, `units`, `ieee`, `quick-script` dialects.
- `egglog` optional backend for `simplify`/`is equivalent to`.
- Python bridge (`use python …`, `needs foreign`, `foreign-item`, `foreign-attribute`).
- `network` host adapter; `CapabilityBacking` protocol + separate `sayform-athome` adapter package (AGPL, outside the core repo).
- Packages, `say lock` with hash and `needs` pinning, `--diff`/`--accept`.
- Property checks (`check for any …`), `say test --laws`, test fakes.
- **Stretch (clearly marked in the repo):** self-hosted formatter and `explain` printer written in Sayform, verified against the Python printers by the round-trip suite.

## 3. v1
Gradual type inference (E0201 inferred, E0208), LSP (hover = English reading + core + symbols), localised keyword dialects, `whichever comes first:` select, real threads/async for blocking calls, C FFI and WASM, subprocess sandbox for `foreign`, `say migrate`, module privacy, shielding (if O-1 resolves yes), edition 1 frozen as `SAY-SPEC-1`.

## 4. Kill criteria (from the seed, unchanged in substance)
| # | Test | Threshold | If it fails |
|---|---|---|---|
| K1 | Readability: 10 people (mixed experience) read 5 programs in words vs symbols vs Python | words beat Python by < 15% on comprehension accuracy, or take > 1.5× the time | drop the words-first stance; keep `explain` |
| K2 | Ambiguity rate: 500-line corpus written by newcomers | > 5% of lines hit E0107/E0108-class errors | the grammar is too English: cut forms |
| K3 | Writing cost (AppleScript test) after 1 hour of learning | words writing > 1.3× slower than Python | make symbols the default writing surface |
| K4 | Capability friction | "hello web" needs > 3 capability lines | redesign defaults |
| K5 | No pull | by v0.1 nobody but Adam has written 100 lines | park; extract `explain` + rulesets as a Python library |
| K6 | Lightweight budget (new, lite pass) | v0 needs a third runtime dependency, or the reference interpreter exceeds 8,000 lines (excluding generated tables and tests) | re-cut scope before adding anything |

## 5. Biggest design risk
English that *looks* free-form makes people write what the grammar cannot parse (Cook 2007). Mitigations, all normative: closed grammar (63 reserved + 89 contextual words, no NLP); a symbols twin for every phrase; formatter fixes one phrasing; ambiguity is an error that shows both readings; articles only in grammar slots; REPL and (v1) LSP show the canonical form as you type.
