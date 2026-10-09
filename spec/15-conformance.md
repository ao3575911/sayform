# 15 · Conformance suite
Spec `0.1-lite` · edition 0. RFC 2119 keywords as in [01-principles.md](01-principles.md).

An implementation **conforms to the v0 profile** when it passes every test below that is not marked v0.1/v1. Test programs are written **in Sayform** (`.say`); expectations are TOML.

## 1. Layout and expectation format
```
conformance/
  <area>/<TEST-ID>.say          # the program (words surface unless the test says otherwise)
  <area>/<TEST-ID>.expect.toml  # expectations
  golden/<G-ID>/                # program.say, program.words.say, program.symbols.say,
                                # explain.txt, core.json, hash.txt, stdout.txt
```
```toml
[expect]
exit = 0                       # 0 | 1 | 2 | 3 | 4 | 5 | 70
stdout = "Hello, world\n"      # exact, optional
diagnostics = ["SAY-E0101"]    # codes in order of report, optional
line = 3                       # line of the first diagnostic, optional
words = "golden/G-01/program.words.say"     # fmt --words must equal this, optional
symbols = "golden/G-01/program.symbols.say" # fmt --symbols must equal this, optional
explain = "golden/G-01/explain.txt"         # optional
hash = "b3:…"                               # optional, full 52-char value
```
A runner (`tests/test_conformance.py`) MUST discover every `*.say` with an `.expect.toml` and run it with the CLI (`say run`, `say check`, `say fmt --check`, `say explain`, `say hash` as needed). Changing a golden file requires a spec change (CHANGELOG entry).

## 2. Lexical (`LEX`) — [02-lexical.md](02-lexical.md)
| ID | Checks |
|---|---|
| LEX-01 | UTF-8 accepted; invalid UTF-8 → E0105 |
| LEX-02 | BOM at offset 0 ignored; elsewhere E0105 |
| LEX-03 | CRLF equals LF; lone CR → E0105 |
| LEX-04 | tab indentation → E0101 |
| LEX-05 | 3-space indentation → E0102 |
| LEX-06 | bracket continuation ignores indentation; backslash continuation → E0105 |
| LEX-07 | trailing `.` discarded and removed by fmt |
| LEX-08 | `total-cost` and `total_cost` are one name; declaring both → E0113 |
| LEX-09 | `x-1` is subtraction; `level_2` → E0105 |
| LEX-10 | `Let` → E0103; type variable `A` accepted |
| LEX-11 | `'s` possessive vs `'x` symbol; stray `'` → E0105 |
| LEX-12 | `007`, `1_000`, `.5`, `5.`, `1e3` → E0135; `approx 1e3` accepted |
| LEX-13 | `12.50` keeps scale 2 in fmt output |
| LEX-14 | text escapes; `\q` → E0136; `\u{1F600}` accepted |
| LEX-15 | unterminated text → E0106 |
| LEX-16 | interpolation `{x + 1}`; `\{` literal brace |
| LEX-17 | `"""` dedent rule |
| LEX-18 | durations `5 seconds`, `5s`, `200ms`, `2 min` |
| LEX-19 | `#` comment kept verbatim through fmt in both surfaces |
| LEX-20 | every reserved word (63) rejected as a name → E0109 (63 sub-cases) |
| LEX-21 | every contextual word (89) usable as a name with W0114 (89 sub-cases) |
| LEX-22 | `≠ ≤ ≥ ∈ ≡` aliases lower like ASCII; `--unicode` prints them |
| LEX-23 | `;`, `@`, `**` → E0105 with hint |
| LEX-24 | non-NFC identifier → E0105; non-ASCII identifier accepted, but E0124 under `strict` |

## 3. Grammar and ambiguity (`GRM`) — [03-grammar.md](03-grammar.md)
| ID | Checks |
|---|---|
| GRM-01 | R1: `let ranked be a list of numbers sorted by size` → E0107 |
| GRM-02 | R1: article outside slot → E0104 |
| GRM-03 | R2: `xs where it > 0 sorted by it` = sort_by(filter) |
| GRM-04 | R2: parenthesised clause inside `where` body |
| GRM-05 | R3: `the name of the owner of car` = `car's owner's name` (same core) |
| GRM-06 | R4: `, descending` attaches to `sorted by`; stray modifier → E0130 |
| GRM-07 | R5/R6: `sum of xs / count of xs` → E0108 with both readings |
| GRM-08 | R6: `if count of xs is at least 3:` parses without error |
| GRM-09 | R6: `show x + 1` → E0108; `show (x + 1)` ok |
| GRM-10 | R7: `copy from a to b` uses slots; `show (from 1 to 3)` is a range |
| GRM-11 | R8: `first of xs` call vs `first of:` block |
| GRM-12 | R9 (v0.1 units): `x in feet` vs membership; clash → E0108 |
| GRM-13 | R10: bare field of `it`; clash with local → E0108 |
| GRM-14 | R11: construction vs named args vs copy-with |
| GRM-15 | R12: `with a 1 and b 2` vs logical `and` |
| GRM-16 | R13: `a or else b` vs `a or b` |
| GRM-17 | R14: `1 < x < 10` lowers to between; `a = b = c` → E0121; `a < b > c` → E0121 |
| GRM-18 | R15: mixed `and`/`or` → W0116; fmt adds brackets |
| GRM-19 | R16: `add 1 to total` statement vs `add(1, 2)` call |
| GRM-20 | R17: `=>` rule in ruleset vs lambda |
| GRM-21 | R20: `List[Number]` is a type value |
| GRM-22 | words function header with all clause kinds, any input order, canonical output order |
| GRM-23 | symbols `def` header equivalent to GRM-22 (same core) |
| GRM-24 | record inline and block forms give the same core |
| GRM-25 | variant words and symbols give the same core |
| GRM-26 | `match` words (`when`, `, if`) and symbols (`case`, `if`) same core |
| GRM-27 | top-level non-`let` statement → E0130 |
| GRM-28 | positional-after-slot parameter → E0407 |
| GRM-29 | `is` adjective → `is-ADJ`; undefined → E0115; value → E0110 |
| GRM-30 | v0.1 declarations (`role`, `plays`, `effect`, `dialect NAME:`) parse and are rejected with E1013 |

## 4. Core AST, lowering, round trip, hash
1. **`AST-01`…`AST-44`**: for each tag, a minimal program producing that node; checks parse, both prints, re-parse equality, `explain` sentence non-empty, and one invariant violation producing the code listed in [04-core-ast.md](04-core-ast.md) §2 (v0.1 tags: E1013). **`AST-T60`…`AST-T68`**, **`AST-P70`…`AST-P78`**: same for sub-nodes.
2. **`LOW-01`…`LOW-NN`**: one test per row of the lowering table ([04-core-ast.md](04-core-ast.md) §3), numbered in row order; each asserts that every listed spelling yields the identical `say core --json` output.
3. **Round-trip properties `RT-L1`…`RT-L7`** (Hypothesis, `tests/roundtrip/`): laws L1–L7 at 200 examples per law per PR, 10,000 nightly, with the generator constraints in [04-core-ast.md](04-core-ast.md) §4. `RT-MUT`: the mutation check MUST fail at least one law. `RT-CORPUS`: every `.say` file in the repository (prelude, examples, conformance) satisfies L3–L5.
4. **Hash `HASH-01`…`HASH-12`:**
   | ID | Checks |
   |---|---|
   | HASH-01 | words and symbols versions of one module hash equal (L5) |
   | HASH-02 | renaming a local leaves the definition hash unchanged |
   | HASH-03 | renaming the function itself leaves its hash unchanged |
   | HASH-04 | renaming a field, slot, case or record type changes the hash |
   | HASH-05 | comments and notes do not change the core hash; notes change the doc hash |
   | HASH-06 | `12.50` and `12.5` literals hash differently; values compare equal |
   | HASH-07 | changing a callee's body changes the caller's hash (Merkle) |
   | HASH-08 | mutually recursive pair hashes deterministically (SCC) |
   | HASH-09 | module hash changes when an export is renamed |
   | HASH-10 | printed form is `b3:` + 52 lowercase base32 characters |
   | HASH-11 | SCS-1 byte vectors for 10 fixed trees match `conformance/hash/vectors.toml` |
   | HASH-12 | unknown tag → E1002 |

## 5. Types and values
`TYP-01`…`TYP-20` (type phrases, plurals, articles F-R6, optional/union, gradual runtime checks E0212, static checks list in [05-types-values.md](05-types-values.md) §1.1). `NUM-01`…`NUM-24`, including: `NUM-01` `0.1 + 0.2 equals 0.3`; `NUM-02` `1 / 4` displays `0.25`; `NUM-03` `1 / 3` displays `1/3`; `NUM-04` scale rules for `+` and `*`; `NUM-05` `//` toward −∞; `NUM-06` `-7 mod 3` is `2`; `NUM-07` `2 ^ -1` is `0.5`; `NUM-08` `0 ^ 0` is `1`; `NUM-09` `(negative 8) ^ (1/3)` panics E0842; `NUM-10` division by zero panics E0841 (exit 70); `NUM-11` `checked-divide 1 by 0` gives problem `division-by-zero`; `NUM-12` approx contagion and `approx` display; `NUM-13` `0.1 equals approx 0.1` is `no`; `NUM-14` `round 2.5` is `2`, `round 3.5` is `4`; `NUM-15` 200-digit integer arithmetic; `NUM-16`…`NUM-24` E0801 sites. `TXT-01`…`TXT-10` (grapheme length of `"e\u{301}"` is 1, emoji ZWJ sequence is 1, code points, UTF-8 bytes, comparison by code point, E0202). `REC-01`…`REC-12` (construction, defaults, E0211, copy-with, invariants → `invalid`, changeable, structural equality includes type name, plural). `COL-01`…`COL-14` (1-based, negative index, inclusive slices, E0181, E0831, E0832, optional index, map lookup, insertion order, order-insensitive equality, `added`).

## 6. Operators (`OPT`) — [06-operators.md](06-operators.md)
`OPT-01`…`OPT-48` and `OPT-S1`…`OPT-S6`: one test file per operator row; each file contains the canonical words form, the canonical symbols form, every accepted alternative spelling, the edge cases in the row, and one program per listed error code. Expected: identical core across spellings; stated results; stated diagnostics.

## 7. Semantics
`SEM-01`…`SEM-40` (evaluation order with side effects via `show`, short-circuit, defaults evaluated per call, explicit return, falling off the end, call depth limit, shadowing, E0301–E0303, exit codes 0/1/2/70). `PAT-01`…`PAT-16` (every pattern form, closed vs `and more`, E0904, E0905, W0911, `strict` error, no-match panic). `ERRV-01`…`ERRV-12` (problem creation, `try`, `or else`, E0207, W0201, panics uncatchable, `main` returning a problem → exit 1). `DSP-01`…`DSP-10` (multiple dispatch on two arguments, most specific, E0401, E0402 at definition, E0403).

## 8. Standard library (`LIB`)
`LIB-<name>` for each of the 74 functions in [12-stdlib.md](12-stdlib.md): normal cases, edge cases, every listed panic/problem. `LIB-PRELUDE-SAY`: the 21 Sayform prelude functions are loaded from `.say` source and pass the same tests.

## 9. Symbolic (`SYM`) — [08-symbolic.md](08-symbolic.md)
`SYM-01` symbol interning and `-`/`_` equality · `SYM-02` quote returns unevaluated core · `SYM-03` unquote splices expression · `SYM-04` unquote splices literal value · `SYM-05` E0901 · `SYM-06` nested quote · `SYM-07` `head of`/`arguments of` · `SYM-08` evaluate with bindings · `SYM-09` evaluate unbound → `not-found` · `SYM-10` evaluate effect without capability → panic E0503 · `SYM-11` ruleset scoping (not applied implicitly) · `SYM-12` E0902 · `SYM-13` E0903 · `SYM-14` repeated pattern variable · `SYM-15` simplify `x * (y + 0)` using algebra → `x * y` · `SYM-16` simplify with distribution, unique minimum · `SYM-17` budget → W0912 and best-so-far · `SYM-18` tie-break by SCS-1 order · `SYM-19` equivalent → yes · `SYM-20` equivalent → no · `SYM-21` equivalent → nothing on budget · `SYM-22` matches returns bindings · `SYM-23` matches returns nothing · `SYM-24` (v0.1, `egglog` extra installed) e-graph backend result cost ≤ fallback cost on SYM-15…21.

## 10. Effects and capabilities (`CAP`) — [09-effects-capabilities.md](09-effects-capabilities.md)
`CAP-01` hello world with `needs console` · `CAP-02` `show` without `needs console` → E0501 · `CAP-03` transitive effect via callee → E0501 · `CAP-04` header `needs` must cover definitions · `CAP-05` `with files limited to "./data"` allows inside, panics E0502 outside subtree · `CAP-06` `read only` blocks `write-text` · `CAP-07` widening → E0504 · `CAP-08` escaped closure after `with` exit → E0502 · `CAP-09` `--deny console` → E0506, exit 4 · `CAP-10` `network` refused by v0 host → E0506 · `CAP-11` `use` grants nothing · `CAP-12` top-level `let` with effect → E0501 · `CAP-13` tests get captured console · `CAP-14` tests: `files` refused without `--allow` · `CAP-15` virtual clock in tests · `CAP-16` seeded random reproducible · `CAP-17` call through function value checked at run time · `CAP-18` `tasks limited to 2` bounds concurrency · `CAP-19` REPL starts with console only · `CAP-20` `CapabilityBacking` stub returning `"revoked"` → `problem capability-revoked`.

## 11. Modules, dialects, lockfile
`MOD-01`…`MOD-14` (header order E0702, path E0701, cycle E0701, `use M: a`, alias, E0305, E1012/W1012, exports, module search). `DIA-01`…`DIA-08` (`strict` effects: E0124, E0205, W0911→error, E0712; unknown dialect E0706; `money`/`units`/`ieee`/`quick-script` → E1013 in v0). `LOCK-01`…`LOCK-06` (v0.1: format, hash pin E0703, needs growth exit 5, `--accept`).

## 12. Concurrency (`CON`) — [11-concurrency.md](11-concurrency.md)
`CON-01` together runs all children · `CON-02` all of → list in source order · `CON-03` labelled all of → record · `CON-04` mixed labels → E0130 · `CON-05` first of → first success, others cancelled · `CON-06` first of all fail → several · `CON-07` single failure unwrapped (D6) · `CON-08` two failures → several in source order · `CON-09` E0606 · `CON-10` panic in child re-panics with child trace · `CON-11` within timeout → timed-out (virtual clock) · `CON-12` nested within earliest deadline · `CON-13` E0605 · `CON-14` E0601 · `CON-15` E0603 · `CON-16` E0604 · `CON-17` unbuffered rendezvous order · `CON-18` buffered channel · `CON-19` receive after close+drain → nothing · `CON-20` E0610, E0611 · `CON-21` deadlock → E0612 · `CON-22` `--shuffle-tasks 7` deterministic output across runs.

## 13. Errors (`ERR`) — [14-errors.md](14-errors.md)
`ERR-<code>` for each of the 96 active codes: minimal program, expected code, line, and for panics exit 70, for H exit 4. `ERR-FORMAT`: 10 diagnostics checked for all 5 parts in text and JSON. `ERR-RETIRED`: no implementation emits E0119 or any group-00 code.

## 14. Tooling (`TOOL`, `FMT`, `EXP`, `TEST`) — [13-tooling.md](13-tooling.md)
`TOOL-01`…`TOOL-20` (every command, flag and exit code in §1; `--json` schema validation; no network access by the CLI). `FMT-R1`…`FMT-R16` (one per formatter rule; each has an input and both expected outputs). `EXP-01`…`EXP-12` (E1–E3 goldens; one template per node family; footnote folding beyond depth 3; L7 totality on the RT generator). `TEST-01`…`TEST-10` (line forms, block form, note examples, E1004, E1005, failure output contains expected/actual/explain).

## 15. Golden programs (`G`) — written in Sayform
Each golden directory holds the program in canonical words, canonical symbols, `explain.txt`, `core.json`, `hash.txt`, `stdout.txt`.
| ID | Program | Covers |
|---|---|---|
| G-01 | hello world | `main`, `needs console`, `show` |
| G-02 | exact decimals and Australian GST at 10% on a list of prices | decimals, scale, `sum of`, `each` |
| G-03 | average with note examples and `empty-list` problem | notes as tests, `may fail with`, `try` |
| G-04 | records and variants: shape areas | records, variants, `match`, guards |
| G-05 | word frequency of a text | `split`, `grouped by`, `sorted by …, descending`, maps |
| G-06 | FizzBuzz 1 to 15 | `repeat`/`for`, `mod`, `if`/`otherwise if` |
| G-07 | binary search over a sorted list | 1-based indexing, `while`, `//` |
| G-08 | algebra simplification | `quote`, `ruleset`, `simplify`, `is equivalent to` |
| G-09 | symbolic derivative of a polynomial expression | `matches`, `head of`, recursion over Expressions |
| G-10 | file line count limited to `./data`, read only | `files`, `with … limited to`, capability refusal path |
| G-11 | fan-out with `all of:` and a deadline | `tasks`, `within`, D6 aggregation |
| G-12 | producer/consumer over a channel | channels, `received from`, close |
| G-13 | dispatch: `add` on a user `Vector` record | multiple dispatch, orphan rule |
| G-14 | the 21 prelude functions' own tests | prelude in Sayform |

### 15.1 G-01 (normative text)
`program.words.say`:
```say
module hello
edition 0
needs console


to main, needs console:
    show "Hello, world"
```
`program.symbols.say`:
```say
module hello
edition 0
needs console


def main() needs console:
    show("Hello, world")
```
`stdout.txt`: `Hello, world` followed by a line end. `explain.txt`:
```
Module hello, edition 0.
It may use: console.
Function `main`: takes nothing; gives nothing; may use console.
L7:   Show the text "Hello, world".
```

### 15.2 G-02 (normative text)
```say
module gst
edition 0
needs console


note: Australian GST is 10% of the GST-exclusive price.
    example: gst of 12.50 gives 1.25
to gst of price (a decimal) giving a decimal:
    give back price * 0.10


to main, needs console:
    let prices be [12.50, 3.20, 0.99]
    let total-gst be sum of (prices each gst of it)
    show "GST: {total-gst}"
    show "Rounded: {round total-gst with places 2}"
```
Expected stdout: `GST: 1.6690` then `Rounded: 1.67`. Derivation: each `price * 0.10` has scale 2 + 2 = 4 (`1.2500`, `0.3200`, `0.0990`); `sum of` starts from `0` and adds with scale = max scale, giving `1.6690`; `round … with places 2` (half-even) gives `1.67`. The note example passes because exact equality ignores scale.

### 15.3 G-08 (normative text)
```say
module algebra-demo
edition 0
needs console


ruleset algebra:
    rewrite ?a + 0 as ?a
    rewrite ?a * 1 as ?a
    rewrite ?a * 0 as 0


to main, needs console:
    let e be quote (x * (y + 0) * 1)
    show simplify e using algebra
    let proven be (quote (x + 0)) is equivalent to quote (x) using algebra
    show proven
```
Expected stdout: `x * y` then `yes` (`display` prints Expressions in the canonical ASCII symbols surface).

The remaining golden programs are authored in milestone M9 of the build prompt and reviewed against this table; their expected outputs MUST be derived by hand from this spec before the implementation is run against them.
