# TRACE — every source item → destination
S = `english-symbolic-language-seed-2026-10-10.md` · F = `sayform-f15-onwards-2026-10-10.md`. "→ CUT" items are recorded in [CHANGELOG.md](CHANGELOG.md).

## Seed (S)
| Source item | Destination |
|---|---|
| S header, legend (FACT/UNKNOWN/OPINION) | 01 §0 tags; 16 header |
| S §0 thesis (3 points, no NLP) | 01 §1 |
| S §1 prior-art table (Inform 7, AppleScript/OXT, COBOL, Hedy, Quorum, Mojo, Nim, Racket, Lark, Julia, Wolfram, egglog, SymPy, Unison, Koka, Austral, Gleam, Roc) | 16 §1 (every row, including COBOL → 05 §3 exact decimals, Quorum → 01 N3, Mojo, OpenXTalk-Beyond, Swift) |
| S §1 recent English-like repos (57, plain-lang 37★, englang 15★) | 16 §2 |
| S §1 "The 5 that matter" | 16 §1 (AppleScript, Racket, egglog/Wolfram, Hedy, Unison/Koka/Roc/Austral rows) |
| S §1 name options (Sayform/Saywell/Termwise), `.say`, `say` | 00 header; 16 §3; 02 §1 |
| S §2 N1–N7 table | 01 §2 |
| S F1 lexical grammar | 02 §1–§4 (C-16, C-17, C-18) |
| S F2 values & types, gradual | 05 §1, §1.1, §2 |
| S F3 binding, mutability | 07 §2; 06 §3 |
| S F4 symbols, quote, evaluate, rewrite, simplify | 08 (all) |
| S F5 functions, calls, slots, lambdas | 07 §3; 03 §5.2–5.3 (C-05, C-06) |
| S F6 control flow | 07 §4 |
| S F7 errors (values, panics, 5-part messages) | 07 §6; 14 §1 |
| S F8 modules & imports | 10 §1 |
| S F9 effects & capabilities | 09 §1–§3 (C-04) |
| S F10 extension mechanism (dialects) | 10 §2; 06 §5 |
| S F11 evaluation model | 07 §1 |
| S F12 equality & identity | 05 §7 |
| S F13 numbers, money, units, division by zero | 05 §3 (C-09, C-22, C-25) |
| S F14 text & Unicode | 05 §4 |
| S F15 one-canonical-form rule | 01 Law 1; 04 §1, §4 |
| S F16 concurrency stance | 11 §1 |
| S §4.1 precedence ladder | 03 §3 |
| S §4.2 operator table (all rows) | 06 §2–§3; 04 §3 (C-07, C-10, C-12, C-14) |
| S §4.3 overload/extension protocol | 06 §5; 07 §8 |
| S §4.4 ambiguity rules 1–5 + worked examples | 03 §4 R1–R5, §4.1 |
| S §4.5 indexing decision | 05 §6 (D1 locked) |
| S §4.6 `or` / `or else` / `and` | 06 §4 |
| S §4.7 declaring operators | 06 §5; 10 §2.8 (v0.1) |
| S §5 innovations I1–I8 | 16 §2 (I1–I8, plus I9) |
| S §5 honest summary | 16 §2 |
| S §6 roadmap v0 / v0.1 / v1 | 17 §1–§3 (re-planned; C-24, C-25, C-27) |
| S §6 kill criteria 1–5 | 17 §4 K1–K5 (+K6) |
| S §6 biggest risk & mitigation | 17 §5 |
| S App A core AST draft | superseded by F §1.1 → 04 §2 |
| S App B reserved words draft | superseded by F23 → 02 §5 |
| S App C sources | 16 §1 and evidence line; re-verified 10 Oct 2026 |
| S update note (D1–D6 locked) | 00 locked-decisions table |

## F15 onwards (F)
| Source item | Destination |
|---|---|
| F §0 legend, ground rules | 01 §0, Laws 1–4 |
| F §0.1 A1 (63 reserved) | 02 §5 |
| F §0.1 A2 (`show` a function) | 12 §2.2 |
| F §0.1 A3 (`added`) | 04 §3; 06 ST-04; 12 #31 |
| F §0.1 A4 (44 nodes) | 04 §2 |
| F §0.1 A5 (`-` ≡ `_`) | 02 §4.1 |
| F §0.1 A6 (out of range panics, `, if any`) | 05 §6; 06 OP-34/36 |
| F §1.0 rule restated | 04 §1 |
| F §1.1 node catalogue (M, S, E families; type and pattern sub-nodes; tags) | 04 §2 (C-19, C-23, C-24) |
| F §1.2 lowering table | 04 §3 |
| F §1.2.1 resolving `in` | 03 §4 R9 |
| F §1.3 round-trip laws L1–L7 and testing (generator, budgets 200/10,000, corpus, goldens, mutation) | 04 §4; 15 §4 |
| F §1.4 formatter rules F-R1–F-R13 | 13 §2 (+F-R14–F-R16, C-39) |
| F §1.5 `explain` grammar, templates, 3 examples | 13 §3 (C-45) |
| F §1.6 core hash: SCS-1 table, BLAKE3, included/excluded, module hash, recursion, rationale | 04 §5–§6 (C-44) |
| F §1.7 comments and notes attachment | 04 §8 |
| F §2.1 concurrency prior art | 16 §1 (Trio, Kotlin, Java, Python, Go; Swift SE-0304 noted in 11 §1) |
| F §2.2 constructs | 11 §2 (C-20) |
| F §2.3 cancellation | 11 §3 |
| F §2.4 error aggregation | 11 §4 (D6) |
| F §2.5 channels | 11 §5 (C-29) |
| F §2.6 timeouts | 11 §6 |
| F §2.7 `tasks` effect and capabilities | 11 §7; 09 §3.5 |
| F §2.8 v0 scheduler | 11 §8 (C-55) |
| F §2.9 F16-Q1/Q2/Q3 | Q1 → D6 (11 §4); Q2 → OPEN O-1; Q3 → 17 §3 (v1) |
| F F17 records (+open: anonymous records) | 05 §5 (anonymous records: decided, 05 §5.8) |
| F F18 collections, indexing evidence and rationale (+open: `xs[-1]`) | 05 §6 (negative index kept); evidence → 16 §1 (Lua, Julia, Dijkstra; MATLAB/Python quotes not re-cited) |
| F F19 pattern grammar (+open: pure guards) | 03-grammar.ebnf §10; 07 §5 (guards pure: decided) |
| F F20 roles and dispatch (+open: default methods) | 07 §8 (default methods: decided, v0.1) |
| F F21 generics (+open: HKT) | 05 §2 (HKT out of scope) |
| F F22 foreign interop table (+open: zero-copy numpy) | 13 §6 (zero-copy: v1, 17 §3 implicit under foreign work) |
| F F23 reserved words, contextual words, stdlib shape | 02 §5–§6 (C-01–C-03); 12 (C-32) |
| F F24 tooling contract, REPL | 13 §1, §4 |
| F F25 testing as syntax (+open: test hash) | 13 §5 (test hash: v0.1, 10 §5.5) |
| F F26 editions, dialect stability (+open: cadence) | 10 §3 (cadence: yearly, OPINION) |
| F F27 security model + lockfile excerpt (+open: signing) | 09 §6; 10 §5 (signing out of scope) |
| F §4 error-code registry (all codes) | 14 §2 (C-31) |
| F §4 runtime problem kinds | 14 §3; 07 §6.1 |
| F §5 decisions D1–D6 | 00 locked-decisions table |
| F App S sources | 16 §1 (re-verified) |

## Coverage check
Every row above has a destination; no source section is unmapped. Items cut by the lite pass are listed in CHANGELOG with their kind (CUT) and remain recoverable in v0.1/v1 where noted.
