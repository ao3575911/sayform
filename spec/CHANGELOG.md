# CHANGELOG — spec 0.1-lite vs the two source documents
Sources: `english-symbolic-language-seed-2026-10-10.md` (seed) and `sayform-f15-onwards-2026-10-10.md` (F15+). Format inspired by [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Kinds: **CUT** (removed or moved to a later profile/dialect, lite pass) · **TIGHTEN** (made precise or consistent, harden pass) · **ADD** (needed to close a gap) · **KEEP** (explicitly unchanged). ⚑ = changes a source decision; all five ⚑ changes ACCEPTED by Adam 2026-10-10.

## Spec 0.1-lite — Sat 10 Oct 2026 (AWST)
### Locked decisions (KEEP)
- D1–D6 kept exactly: 1-based indexing in both surfaces with `xs[0]` = E0181; hash ignores local names and the function's own name and includes field/slot/type/export names; `-` ≡ `_`; `first of:` = first success; 63 reserved words + closed contextual list, `show` a function; single concurrent problem unwrapped, 2+ → `several`.
- Amendments A1–A6 of F15+ kept (A3 `added`, A5 `-`/`_`, A6 out-of-range panic E0832).

### Lexical and keywords
| # | Kind | Change | Why |
|---|---|---|---|
| C-01 | TIGHTEN | Contextual-word list rebuilt and closed at **89** words, each with its slot. Added: operator words `plus minus divided mod negative power`, `times` in operator position, `item`, `problem`, `approx` (kept), `matches`, `equivalent`, `default`, `plural`, `read`, `only`, `exclusive above below`, `symbol`, `type`, `into`, `add`, symbols openers `def elif break continue record variant case`, `all-of first-of`, `time`, time units, `explained`. | The source grammar used ~30 words that were in neither list; keyword list must match the grammar. |
| C-02 | CUT | `uses` header keyword removed; imports are `use` lines. | One spelling. |
| C-03 | CUT | Contextual `holding` (→ `with capacity`), `its`, `whichever`, `comes` (select is v1), `empty` (adjectives are open). | Fewer words. |
| C-07 | CUT | `#c` (count) and `Σ` removed. | `#` starts a comment; ASCII must suffice. |
| C-08 | CUT | `0.1f` float suffix removed; only `approx 0.1`. | One spelling. |
| C-15 | TIGHTEN | Predicates are named `is-ADJ` (was `empty?`); `?` cannot appear in names. | `?` is already try, optional access and pattern variables. |
| C-16 | TIGHTEN | `'` removed from identifier characters; joiners `-`/`_` must be followed by a letter (`level_2` invalid). | Conflicts with `'s`/`'x`; guarantees `-`↔`_` round trip (`level-2` would re-lex as subtraction). |
| C-17 | CUT | Implicit continuation after a trailing operator word removed; continuation only inside brackets. | Lexer must not depend on the operator table. |
| C-18 | TIGHTEN | No leading zeros, digit separators or bare exponents (E0135). | One literal spelling per value. |
| C-12 | CUT | Accepted synonyms removed: `is equal to` (for `equals`), `no more than`, `no less than`, `more than`, `total of`, `how many in`, `a squared`, `remainder of a by b`, `t in uppercase` (→ `uppercase of t`), `second`, `isn't`. Kept: `contains`, `true`/`false`, `==` (reserved/familiar). | Smaller grammar, fewer ambiguity paths. |
| C-13 | CUT | `its` removed; E0119 retired. | Parse-only sugar that always reprinted as the explicit possessor. |

### Grammar
| # | Kind | Change | Why |
|---|---|---|---|
| C-05 ⚑ | TIGHTEN | Function names are single (hyphenated) words. Source examples `count adults in`, `fastest forecast for`, `fetch forecast` rewritten as `count-adults of`, `fastest-forecast for`, `fetch-forecast for`. | The seed's F1 forbids spaces in names; multi-word names made calls undecidable. Alternative: a declared multi-word verb table per module (rejected as heavier). |
| C-06 ⚑ | TIGHTEN | Slot words are exactly `to from by into for`; `of` is a first-parameter lead; `with` introduces named arguments. `in`, `as`, `with` as preposition slots removed. | `in` collides with membership, `as` with `use … as`/`rewrite … as`, `with` with named arguments and record construction. Alternative: keep `in` and require parentheses on membership inside calls. |
| C-11 ⚑ | ADD | Prefix-call rule R6: the argument of a words call `f x` is P11+ plus postfix clauses; a following arithmetic operator is E0108 (`show x + 1`, `sum of xs / count of xs`). | Removes a silent-misparse class. Alternative: argument extends to clause end (Haskell `$`), which silently turns `sum of xs / 2` into `sum(xs / 2)`. |
| C-37 | TIGHTEN | `the f of x` is always field access; `f of x` (no article) is a call. | Resolves the source's double use of `of`. |
| C-38 | TIGHTEN | Seed example `the size of the first of xs` → `size of first of xs`. | Follows C-37. |
| C-10 | TIGHTEN | Comparison chains limited to the 3-operand between form (E0121); the `chain` builtin removed; `between` gains low/high inclusivity (`, exclusive [above\|below]`). | General chains had no words print, breaking L1. |
| C-20 | CUT | `within` is a statement only; `let r be within 2 seconds: …` removed. | Statement blocks have no value in edition 0. |
| C-19 | CUT | Lambda bodies are expressions only (catalogue field `Lambda.body: Expr`). | No multi-line lambda syntax in a Python-shaped layout. |
| C-34 | TIGHTEN | Top level allows declarations, notes, checks and immutable pure `let`s only (E0130). | Executable code lives in `main`; keeps capabilities rooted in one place. |
| C-35 | TIGHTEN | `repeat n times` lowers to `For(PWild, range(1, n))`; symbols print `for _ in 1..n:`. | Gives the construct a symbols twin. |
| C-36 | TIGHTEN | Records: symbols `var record` for changeable, `(plural …)` in both surfaces, block form `has:`; variant cases one per line in both surfaces (no inline `\|`). | Every core field must print in both surfaces (L1/L2). |
| C-40 | TIGHTEN | Header order: module, edition, use, needs, dialect; `edition` optional with W1012 (error under `strict`); `module` optional for single-file programs. | Matches the catalogue; lighter scripts. |
| C-50 | TIGHTEN | `check` relation (`equals`/`is`/`matches`/`holds`) is derived from the top node of the checked expression. | One grammar rule instead of five. |
| C-33 | TIGHTEN | Star imports are banned everywhere (was `strict` only). | Every import visible in the header. |

### Semantics and values
| # | Kind | Change | Why |
|---|---|---|---|
| C-04 ⚑ | TIGHTEN | `main` takes no `system` parameter. Root capabilities = `main`'s declared `needs` ∩ host policy. `with EFFECT limited to X:` (both surfaces) replaces `with system's network limited to …` / `with system.network.limit(…)`. Callees receive the caller's capabilities implicitly, restricted to their own declared `needs`. | One mechanism, checked statically; meets kill criterion 4. Alternative: explicit capability parameters everywhere (more ceremony). |
| C-09 ⚑ | TIGHTEN | Exact division/floor-division/modulo by zero **panics** (E0841) instead of returning `problem(division-by-zero)`; `checked-divide a by b` returns the problem. | With typed `may fail with`, a problem-returning `/` would make every arithmetic expression fallible. Alternative: keep the problem and add `division-by-zero` to every numeric signature. |
| C-21 | TIGHTEN | No `ok(…)` wrapper or `Result` type: fallible functions return a value or a problem; `problem KIND` is a contextual constructor. | Lighter; `try`/`or else` unchanged. |
| C-22 | TIGHTEN | `Approx` is disjoint from exact numbers (seed said Integer ⊂ Rational ⊂ Real-approx). Normalisation for `/` and Rational results: Integer → terminating Decimal → Rational. Decimal scale rules for `+ - *` specified. | Deterministic display (`1 / 4` → `0.25`). |
| C-52 | TIGHTEN | Rounding is `round x with places n [with mode …]`, half-even default (was `rounded to cents, half-even`). | No new words. |
| C-46 | TIGHTEN | Text indexing undefined in edition 0. | Grapheme indexing is costly and rarely needed. |
| C-47 | ADD | Map lookup `m[k]` / `m?[k]`; missing key panics E0832. | Gap in source. |
| C-42 | ADD | Duplicate literal set items → E0821. | Consistency with maps. |
| C-48 | ADD | Cyclic imports → E0701. | Simple load order. |
| C-23 | TIGHTEN | Pattern variables inside rules/quote patterns are `Name` with `ref = PatVar(i)`; no new node. | Keeps the catalogue at 44. |
| C-43 | ADD | `display` specified; Expressions display in canonical ASCII symbols. | Deterministic output. |

### Lite profile and dialects
| # | Kind | Change | Why |
|---|---|---|---|
| C-24 | CUT | v0 profile = 40 of 44 nodes; `RoleDef`, `Plays`, `EffectDef`, `OperatorDef` move to v0.1 (parsed, rejected with E1013). | Smallest core that keeps every law. |
| C-25 | CUT | `money`, `units`, `ieee`, `quick-script` are optional v0.1 dialects; the core keeps only time durations; `strict` ships in v0. | Lightweight core; N6 still served by dialects. |
| C-27 | CUT | Property checks and `--laws` to v0.1. | Would make `hypothesis` a runtime dependency. |
| C-28 | CUT | Network fakes in tests to v0.1; v0 tests get captured console, virtual clock and tasks, seeded random. | v0 host has no network. |
| C-29 | TIGHTEN | `new-channel holding 10` → `new-channel with capacity 10`; `tasks limited to 8 at once` → `tasks limited to 8`. | No extra words. |
| C-30 | TIGHTEN | F16-Q1 resolved by D6; F16-Q3 `select` → v1; F16-Q2 stays open (O-1). | |
| C-14 | CUT | `first 3 of c` → `take 3 from c` (and `drop 3 from c`). | `first` is both a function and a block opener; one meaning per phrase. |
| C-26 | ADD | Python bridge: `foreign-attribute "name" of mod` for Python names that are not Sayform words. | C-16 makes some names unrepresentable. |
| C-32 | TIGHTEN | Builtins fixed at 74 (53 host + 21 written in Sayform); `compare`/`Order` to v0.1; added `display`, `ask`, `head`, `arguments`, `checked-divide`, `drop`, `parse-number`, `received`; `take n from c` replaces `first n of c` (C-14). | Numeric budget; library exercises the language. |

### Core, hash, tooling, errors
| # | Kind | Change | Why |
|---|---|---|---|
| C-44 | TIGHTEN | SCS-1: `Name` symbol text omitted (only `ref`), `PatVar` and `SCC` ref kinds, SCC member hashing specified, canonical NaN pattern given. | Makes D2 mechanically true. |
| C-39 | TIGHTEN | Formatter: F-R14 (call printing), F-R15 (between), F-R16 (repeat) added; continuation indent 4 inside brackets (was 8 inside / 4 outside, but outside continuation no longer exists). | Every core node has one canonical print. |
| C-45 | TIGHTEN | `explain` examples use `edition 0` (current until SAY-SPEC-1) and hyphenated names; full template table for every node (L7). | Consistency. |
| C-31 | TIGHTEN | Error registry: +17 codes (E0121, E0124, E0126, E0130, E0131, E0135, E0136, E0212, E0408, E0409, E0410, E0506, E0612, E0706, E0841, E0842, E1013); E0119 retired; templates for every code; 96 active. | Every operator and node needs an error path; generic syntax error was missing. |
| C-41 | TIGHTEN | RFC 2119 wording throughout; numeric budgets (Law 5); v0 runtime dependencies fixed at 2. | Harden pass. |
| C-53 | TIGHTEN | Unicode version pinned at 15.1.0 for grapheme and identifier properties. | Determinism across hosts. |
| C-54 | ADD | `say core` command (stable JSON of the core) for conformance tests. | Lowering tests need an observable core. |
| C-55 | ADD | Scheduler deadlock detection (E0612); timer heap tie-break by sequence number. | Determinism; previously unspecified. |
