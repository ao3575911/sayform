# 01 · Principles, needs and design laws
Spec `0.1-lite` · edition 0 · Sat 10 Oct 2026 (AWST)

The key words MUST, MUST NOT, REQUIRED, SHALL, SHALL NOT, SHOULD, SHOULD NOT, RECOMMENDED, MAY and OPTIONAL in this spec are to be interpreted as described in BCP 14 ([RFC 2119](https://www.rfc-editor.org/rfc/rfc2119), [RFC 8174](https://www.rfc-editor.org/rfc/rfc8174)) when, and only when, they appear in all capitals.

Tags: **FACT** = checked live on 10 Oct 2026 (source in [16-prior-art.md](16-prior-art.md)) · **OPINION** = design judgement · **UNKNOWN** = not verified.

## 1. Thesis
Code is now written faster than people can review it. The scarce resource is **reading and trusting** code. Sayform is a small, Python-shaped language in which:
1. every program has **one canonical core form** that prints both as plain English (`--words`) and as compact symbols (`--symbols`);
2. every function **says what it may touch** (`needs network`), and those claims are enforced as capabilities;
3. **expressions are data**: quoting, scoped rewrite rules and simplification are part of the core.

English is used to make code **readable**. It is never used to guess what code means: the grammar is closed and deterministic, and contains no natural-language processing (the AppleScript lesson, [16-prior-art.md](16-prior-art.md) §AppleScript).

## 2. Needs (N1–N7)
| # | Need | Evidence | Sayform answer | Where |
|---|---|---|---|---|
| N1 | Make generated code easy to review | FACT: Stack Overflow 2025 survey: 46% distrust AI output accuracy, 33% trust it, about 3% highly trust it; top frustration "almost right, but not quite" (survey page 66%, SO blog 45%; the two sources disagree). FACT: METR early-2025 RCT: experienced OSS developers 19% slower with AI while believing they were 20% faster; Feb 2026 update mixed, with a selection-bias caveat | `say explain`: one English sentence per core node; capability header on every module | [13-tooling.md](13-tooling.md) §3 |
| N2 | Know what code can touch | FACT: Sonatype 2026 report: 454,600+ new malicious packages in 2025, 1.233M total, >99% on npm | Effects are capabilities; imports grant nothing; the lockfile records every package's `needs` and fails on growth | [09-effects-capabilities.md](09-effects-capabilities.md), [10-modules-dialects.md](10-modules-dialects.md) §5 |
| N3 | Syntax novices can read | FACT: Stefik & Siebert 2013 (ACM TOCE): novices using Perl or Java were no more accurate than with a randomly designed language; Python, Ruby and Quorum did better | A closed set of English keywords; minimal punctuation | [02-lexical.md](02-lexical.md) |
| N4 | Keep Python's reach | FACT: SO 2025: Python used by 58% (+7 pp; from a secondary summary, confirm on page) | Python-shaped layout; v0 reference interpreter in Python; Python bridge in v0.1 | [13-tooling.md](13-tooling.md) §6 |
| N5 | Extensibility that never spreads globally | OPINION (Wolfram global rules, monkeypatching, AppleScript term collisions) | Dialects scoped to one module and declared in its header | [10-modules-dialects.md](10-modules-dialects.md) |
| N6 | Correct money, units and exact numbers | OPINION (`0.1 + 0.2`, Mars Climate Orbiter 1999; common knowledge, not re-sourced) | Exact numbers by default; `money` and `units` as optional dialects | [05-types-values.md](05-types-values.md) §3 |
| N7 | Symbolic reasoning as everyday code | OPINION; FACT: egglog is actively developed (pushed 2026-10-09) | `quote`, `ruleset`, `rewrite`, `simplify`, `is equivalent to` | [08-symbolic.md](08-symbolic.md) |

## 3. Design laws (normative)
Each law is binding on the language, on every implementation and on every later edition. A change to a law requires a new spec major version.

### Law 1 · One canonical form
1. Every accepted surface phrasing (words, symbols, a mix of the two, or dialect sugar) MUST lower to exactly one core tree ([04-core-ast.md](04-core-ast.md)).
2. The core tree MUST print in exactly two canonical surfaces, words and symbols, and parsing either print MUST give back the same core (laws L1–L2).
3. The formatter is part of the language. There is exactly one canonical printed form per surface.
4. The core hash MUST be computed over the core, so rewording is never a semantic change.

### Law 2 · No ambient authority
1. A function MUST declare every effect it can perform (`needs …`).
2. At run time every effect MUST be backed by a capability held in the lexical capability context ([09-effects-capabilities.md](09-effects-capabilities.md)).
3. `use` MUST NOT grant capabilities. `evaluate` MUST NOT gain capabilities. Tests hold no real capabilities by default.
4. The only source of root capabilities is the host, through `main`'s declared `needs`, filtered by host policy.

### Law 3 · No global extension
1. Dialects, rulesets and methods are scoped to the module that declares or enables them. Nothing MAY reopen a built-in type, keyword or operator.
2. A dialect MUST lower to the core. It MUST NOT add evaluation semantics.
3. Conflicts between two active dialects MUST be compile errors, never silently resolved.
4. Methods obey the orphan rule (F20, [07-semantics.md](07-semantics.md) §8).

### Law 4 · Ambiguity is an error
1. The grammar MUST be deterministic. Where a line admits two readings that the grammar rules in [03-grammar.md](03-grammar.md) §4 do not settle, the implementation MUST report SAY-E0108 and show both readings plus the symbols form to write instead.
2. There is no truthiness, no implicit Text↔Number conversion and no implicit coercion between unrelated types.
3. `=` is never assignment.

### Law 5 · Lightweight budget
The language and the v0 reference implementation MUST stay within these hard budgets. Raising a budget requires an edition change and a CHANGELOG entry.

| Budget | Edition 0 value |
|---|---|
| Reserved words | **63** exactly ([02-lexical.md](02-lexical.md) §5) |
| Contextual words | **89** exactly, closed list ([02-lexical.md](02-lexical.md) §6) |
| Core node catalogue | **44** tagged nodes (permanent tags) |
| v0 core profile (nodes a v0 implementation MUST support) | **40** (tags 06, 07, 08, 11 are v0.1) |
| Type sub-nodes / pattern sub-nodes | **9** / **9** |
| Precedence levels | **16** (P0–P15; P13 reserved, unused in core) |
| v0 builtin functions | **74** (53 host primitives + 21 written in Sayform), listed in [12-stdlib.md](12-stdlib.md) |
| Built-in effects | **9** |
| v0 runtime dependencies (reference interpreter) | **2**: `lark`, `blake3` (dev only: `pytest`, `hypothesis`; optional extra: `egglog`) |
| Non-ASCII characters required to write any program | **0** (all non-ASCII operators are optional aliases) |
| Reference interpreter size target (OPINION) | ≤ 8,000 lines of Python excluding generated tables and tests |

### Law 6 · Errors are part of the language
1. Every diagnostic MUST have 5 parts: (1) location, (2) a plain-English *what*, (3) a *why*, (4) one *try this*, (5) a stable code `SAY-Exxxx` / `SAY-Wxxxx`.
2. Each code has a conformance test. Codes are never reused ([14-errors.md](14-errors.md)).

### Law 7 · Real characters only
Every character the language assigns a meaning to is a real Unicode scalar value with its code point listed in [02-lexical.md](02-lexical.md) §3. No invented glyphs, no private-use code points, no images. Every prior-art credit links a live source ([16-prior-art.md](16-prior-art.md)).

## 4. Values the design trades for
| We choose | Over | Why (OPINION) |
|---|---|---|
| Readability by reviewers | Writing speed in the words surface | Symbols surface exists for fast writing; both are one core |
| Exactness | Raw numeric speed | `approx` is one word away |
| Explicit effects | Zero-ceremony scripts | Kill criterion 4 caps the ceremony at 3 lines for "hello web" |
| Errors that show both readings | Clever disambiguation | AppleScript lesson |
| A small closed core | A big standard library | Everything else is a module or a dialect |
