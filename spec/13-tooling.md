# 13 · Tooling contract: `say` CLI, formatter, explain, REPL, tests, Python bridge (F22, F24, F25)
Spec `0.1-lite` · edition 0. RFC 2119 keywords as in [01-principles.md](01-principles.md).

## 1. Commands
| Command | Does | Output | Exit codes | Profile |
|---|---|---|---|---|
| `say run FILE [-- ARGS]` | check, then run `main` with the root capabilities policy allows | program output on stdout; diagnostics on stderr | 0 ok · 1 `main` returned a problem · 2 compile errors · 4 capability refused · 70 panic | v0 |
| `say fmt [--words\|--symbols] [--unicode] [--check] PATH…` | normalise (§2) | rewrites files; with `--check`, prints a unified diff | 0 · 1 changes needed (`--check`) · 2 | v0 |
| `say explain FILE[:LINE] [--json]` | §3 grammar | text or JSON | 0 · 2 | v0 |
| `say check PATH… [--strict] [--json]` | parse, resolve, static checks ([05-types-values.md](05-types-values.md) §1.1), effects, capabilities, exhaustiveness | 5-part diagnostics | 0 · 2 | v0 |
| `say test PATH… [--allow EFFECT]… [--shuffle-tasks SEED] [--json]` | §5 | summary or TAP-like JSON | 0 · 3 test failures · 2 | v0 |
| `say hash PATH… [--defs]` | SCS-1 + BLAKE3 | `b3:…  module.name` per module; per definition with `--defs` | 0 · 2 | v0 |
| `say core FILE [--json]` | print the core tree (debugging; stable JSON schema) | text / JSON | 0 · 2 | v0 |
| `say` (no arguments) | REPL (§4) | | | v0 |
| `say lock [--diff] [--accept PKG]` | resolve packages, pin hashes and `needs` | `say.lock` | 0 · 5 needs grew | v0.1 |
| `say migrate --to-edition N` | edition rewrites | rewritten files | 0 · 2 | v1 |
| `say test --laws` | role/operator law properties | | | v0.1 |

1. All commands accept `--json`; JSON outputs are versioned `say-json/1` and documented in the repository (`docs/json-schema/`).
2. Diagnostics go to stderr, program output to stdout. Colours only when stderr is a TTY and `NO_COLOR` is unset.
3. The CLI MUST NOT perform network access except through a granted `network` capability of the program being run (and `say lock`, v0.1).

## 2. Formatter rules (`say fmt`)
| # | Rule |
|---|---|
| F-R1 | Width **88** columns (OPINION; the Black default, FACT per Black docs). Break at the lowest-precedence operator first, then after commas between slots/arguments; continuation lines exist only inside brackets (the formatter adds parentheses if needed); continuation indent 4 inside brackets. |
| F-R2 | One surface per file, chosen by `say.toml` `surface = "words" \| "symbols"` (default `words`), overridden by `--words`/`--symbols`. Mixed files are reprinted entirely in the chosen surface. |
| F-R3 | Canonical words: `let … be`, `set … to`, `give back`, `otherwise if`, `otherwise`, `equals`, `is not equal to`, `is at least`, `is at most`, `is in` (never `contains`), `divided by`, `or else`, `yes`/`no`, `for each … in`, `stop`, `skip`. |
| F-R4 | Canonical symbols: `=` (never `==`), `!=`, `<=`, `>=` (ASCII; `--unicode` prints `≠ ≤ ≥ ∈ ≡`), `:=`, `+=`, `return`, `elif`, `else`, `break`, `continue`, `??`, `\|>`, `!`, `&&`, `\|\|`, `def`, `record`, `variant`, `case`. |
| F-R5 | Possession in words: `x's f` when the possessor is a name or a chain of at most 2 links; `the f of (…)` otherwise. Symbols: always `x.f`. |
| F-R6 | Articles only in type slots: `an` before a vowel letter, else `a`, with the closed exception table ([05-types-values.md](05-types-values.md) §2). Plurals from declarations, else `s`/`es`. |
| F-R7 | Dialect sugar printed only if the dialect is in the header; else as the lowered call. |
| F-R8 | Implicit structure made explicit: a postfix clause inside a prefix-call argument gets parentheses (`count of (people where …)`); mixed `and`/`or` get parentheses. |
| F-R9 | Literals: decimal scale kept; money `12.50 AUD` (words) / `A$12.50` (symbols, registered prefixes only); text re-escaped minimally (`\"`, `\\`, `\{`, `\}`, `\n`, `\t`; other characters literal except C0/C1 controls, which use `\u{…}`). |
| F-R10 | Header order: module, edition, use (sorted by path), needs (effects sorted, with narrowings), dialect (sorted). |
| F-R11 | Function header order: params, `giving`, `needs`, `may fail with` (kinds sorted, joined by `and`), `for any`. |
| F-R12 | Trailing `.` removed. Blank lines: at most 1 inside a block, exactly 2 between top-level declarations. `#` comment text kept verbatim. |
| F-R13 | Identifiers: `-` in words, `_` in symbols (D3). |
| F-R14 | Calls in words: prefix form with the callee's declared lead when there is at most one positional argument and the callee is a name; otherwise paren form `f(a, b, slot=v)`. Arguments below P11 are parenthesised. |
| F-R15 | `between` prints as `x is between lo and hi[, exclusive[ above\|below]]` (words) and `lo <= x <= hi` style (symbols). |
| F-R16 | `For(PWild, range(1, n))` prints `repeat n times:` (words) / `for _ in 1..n:` (symbols). |

`say fmt` MUST satisfy L3 (idempotence) and MUST NOT change the core (L4).

## 3. `say explain`
### 3.1 Output grammar
```
explanation  := header NL { decl-expl }
header       := "Module " QNAME ", edition " INT "." NL
                "It may use: " caps "." NL                 (caps = "nothing" when the row is empty)
decl-expl    := sig-line NL [ note-line NL ] { line NL }
sig-line     := "Function `" NAME "`: takes " params "; gives " type-np "; may use " caps
                [ "; may fail with " kinds ] "."
note-line    := "(Note: " TEXT ")"
line         := "L" INT ": " INDENT sentence               (2 spaces of INDENT per block level)
sentence     := clause "."                                 (one per statement node, capitalised)
noun-phrase  := template(expression node)                  (beyond depth 3, fold into "(1)" footnotes)
footnote     := "    where (" INT ") is " noun-phrase "."
```
Records and variants explain as "Record `Person`: has a name (text) and an age (an integer, default 0); every Person must satisfy: age is at least 0."

### 3.2 Templates (every core node has one; L7)
| Node | Template |
|---|---|
| Bind | "Let `x` be NP, which never changes" / "…, which can change later" |
| Rebind | "Change `x` to NP" |
| SetField | "Change p's f to NP" |
| If | "If NP:" / "Otherwise, if NP:" / "Otherwise:" |
| Match | "Look at NP:" then "When it is PATTERN[, if NP]:" / "Otherwise:" |
| For | "For each `x` in NP:" (PWild: "Repeat N times:") |
| While | "While NP:" |
| Stop / Skip | "Stop the loop" / "Skip to the next item" |
| Return | "Give back NP" (no value: "Give back nothing") |
| ExprStmt | NP (e.g. "Show the total") |
| WithCap | "Using only EFFECT limited to NP[, read only]:" |
| Concurrent | together: "Run these at the same time and wait for all of them:" · all: "Run these at the same time and collect every result:" · first: "Run these at the same time; keep the first that succeeds and cancel the rest:" (children labelled (a), (b), …) |
| Within | "Within NP, otherwise fail with timed-out:" |
| Check | "Check that NP" |
| Try | "NP, stopping here and passing on any problem" |
| Call | the callee's template (`add`: "{a} plus {b}", `count`: "the number of items in {c}", `filter`: "{c} whose {cond}" …); user functions: "the result of NAME given ARGS" (v0.1: `explained as`) |
| Get / Index | "x's f" / "item i of c" (optional: "…, if any") |
| Lit / Interp / SymLit / Name | the literal as written in words / "the text \"…\"" / "the symbol x" / "`name`" |
| Lambda | "a function that, given x, gives NP" |
| ListLit / MapLit / SetLit / RecordLit | "the list (…)" / "the map (…)" / "the set (…)" / "a Person with name … and age …" |
| TypeTest / TypeExpr | "NP is a TYPE" / "the type TYPE" |
| Quote / Unquote | "the expression `…`" / "the value of NP spliced in" |
| Module, Func, RecordDef, VariantDef, Ruleset, Rule, Use, Block, v0.1 nodes | header / sig-line / record line / "Ruleset `r`:" / "Rewrite L as R[, when G]" / "Uses M" / (no sentence; children) / "Declares …" |
`explain` prints what the core means, never the surface the author used.

### 3.3 Examples (golden files in the conformance suite)
**E1 · rewording is not a change**
```say
let area be r's width times r's height
let area = r.width * r.height
```
Both give `L1: Let `area` be r's width times r's height, which never changes.` and the same core hash.

**E2 · implicit `it` and a postfix clause**
```say
module club.members
edition 0
to count-adults of people (a list of Person) giving an integer:
    give back count of (people where age is at least 18)
```
(Slot words are exactly `to from by into for`; the source docs' `count adults in people` header is not valid edition 0 syntax, see CHANGELOG C-11.)
```
Module club.members, edition 0.
It may use: nothing.
Function `count-adults`: takes people (a list of Person); gives an integer; may use nothing.
L4:   Give back the number of items in people whose age is at least 18.
```

**E3 · a race with a deadline**
```say
to fastest-forecast for city (text) giving a Forecast, needs network and tasks, may fail with several and timed-out:
    within 3 seconds:
        give back first of:
            fetch-forecast for city from "bom"
            fetch-forecast for city from "backup"
```
```
Function `fastest-forecast`: takes for city (text); gives a Forecast; may use network and tasks; may fail with several and timed-out.
L2:   Within 3 seconds, otherwise fail with timed-out:
L3:     Give back the first of these to succeed, run at the same time, cancelling the rest:
L4:       (a) the result of fetch-forecast given for city, from "bom".
L5:       (b) the result of fetch-forecast given for city, from "backup".
```

## 4. REPL
1. Echoes each input in the canonical form of the chosen surface.
2. Commands: `:words`, `:symbols`, `:explain EXPR`, `:core EXPR`, `:type EXPR`, `:hash NAME`, `:load FILE`, `:caps`, `:grant EFFECT [limited to X]` (asks for confirmation), `:quit`.
3. Starts with `console` only. Approx values are marked `approx`.

## 5. Testing as syntax (F25)
1. **Line forms:** `check that E equals V` · `check that E` (Truth) · `check that E is P` · `check that E fails with KIND` · `check that E matches PATTERN`; symbols `check E = V`, `check E`, `check E is P`, `check E fails KIND`, `check E ~= P`.
2. **Block form:** `check "label":` with statements and line checks.
3. **Examples in notes are tests:** inside `note:`, a line `example: CALL gives VALUE` or `example: CALL fails with KIND` runs under `say test` (the same idea as Python's `doctest`, FACT). Malformed example lines: SAY-E1005.
4. Checks appear only at module top level and in `*.test.say` files, never inside functions (SAY-E1004). `say run` ignores them.
5. **Capabilities in tests:** captured fake `console`, virtual `clock`/`tasks`, seeded `random`; real effects need `--allow` and are listed in the report.
6. **Failure output:** the 5-part format with *expected*, *actual* and the `explain` sentence for the subject.
7. **Property form** `check for any n (an integer): …` and `--laws` are v0.1 (they need a generator library; Hypothesis-style shrinking is the model).
```say
note: The mean of a list of numbers.
    example: average of [1, 2, 3] gives 2
    example: average of [] fails with empty-list
to average of numbers (a list of numbers) giving a number, may fail with empty-list:
    if numbers is empty:
        give back problem empty-list
    give back (sum of numbers) / (count of numbers)


check "exact decimals":
    check that 0.1 + 0.2 equals 0.3
    check that 1 / 4 equals 0.25
```

## 6. Python bridge (F22, v0.1)
1. `use python numpy as np` requires the module to declare `needs foreign`; every call into Python needs the `foreign` capability.
2. Conversions:
   | Sayform | Python | Back |
   |---|---|---|
   | Integer / Rational / Decimal | `int` / `fractions.Fraction` / `decimal.Decimal` | same |
   | Approx | `float` | Approx (marked) |
   | Text / Truth / Nothing | `str` / `bool` / `None` | same |
   | List / Map / Set | `list` / `dict` / `set` (copied out, frozen back) | same |
   | Record | frozen dataclass proxy | — |
   | other Python object | — | opaque `Foreign` handle; attributes by possession, calls by call forms |
   | Python exception | — | `problem foreign-error` (never a panic) |
3. Names: Python `read_csv` is `read-csv` in words and `read_csv` in symbols (D3). Python names that are not valid Sayform words (e.g. `utf_8`, `__len__`) are reached with `foreign-attribute "utf_8" of mod`.
4. `[ ]` on a `Foreign` value is SAY-E0711; use `foreign-item 0 of arr`, which passes the key unchanged (Sayform's 1-based rule never applies to foreign values).
5. `foreign` is unbounded: lockfile diffs flag it; `strict` refuses it (SAY-E0712) unless narrowed to `foreign limited to "subprocess"` (v1 sandbox).
6. C FFI and WASM are v1.
7. FACT: PyPI `egglog` 14.0.0 (Python ≥ 3.12) can serve as the e-graph backend through this bridge or directly from the host.

## 7. LSP (v1)
Hover shows the `explain` sentence, the core and the symbols form; diagnostics are the 5-part messages; formatting is `say fmt`; hashing is incremental.

## 8. Conformance
`TOOL-01`…`TOOL-20`, `FMT-R1`…`FMT-R16`, `EXP-01`…`EXP-12`, `TEST-01`…`TEST-10` in [15-conformance.md](15-conformance.md).
