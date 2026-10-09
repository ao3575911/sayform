# 16 · Prior art: what Sayform recycles, from whom, and what is new
Spec `0.1-lite`. Every URL below returned HTTP 200 (or a GitHub API record) when checked on **Sat 10 Oct 2026, 06:00–06:40 AWST** with `gh api` or `curl -L`. Star counts and push dates are FACT as of that check (GitHub API, push times converted from UTC). Items marked **OPINION** are judgements; **UNKNOWN** means not verified.

## 1. Recycled ideas
| Source | Link (verified) | Live status (FACT) | What Sayform takes | What it avoids |
|---|---|---|---|---|
| **Racket `#lang`** | https://github.com/racket/racket · https://docs.racket-lang.org/guide/hash-languages.html | 5,217★, pushed 2026-10-10 | per-module languages → **dialects declared in the header**; hygienic expansion | S-expression surface (OPINION: deters mainstream readers) |
| **egglog** | https://github.com/egraphs-good/egglog · https://github.com/egraphs-good/egglog-python · https://egglog-python.readthedocs.io/ | 855★ (MIT, pushed 2026-10-10); Python bindings 111★, PyPI `egglog` 14.0.0, Python ≥ 3.12 | equality saturation + Datalog as the **`simplify` / `is equivalent to` backend** (optional extra) | being a surface language |
| **egg** | https://github.com/egraphs-good/egg | 1,843★, MIT | e-graph cost-based extraction idea (min-cost term) | — |
| **Unison** | https://github.com/unisonweb/unison · https://www.unison-lang.org/docs/the-big-idea/ | 6,747★ | **content-addressed definitions** ("names … don't affect the function's hash"); hash over the core | a codebase manager instead of files in git (OPINION) |
| **Koka** | https://github.com/koka-lang/koka · https://koka-lang.github.io/koka/doc/book.html | 4,090★ | row-typed effects → **`needs` rows**, inferred and checked | academic syntax |
| **Roc** | https://github.com/roc-lang/roc · https://www.roc-lang.org/platforms | 6,100★, UPL-1.0 | platform/app split → **host grants root capabilities to `main`** | — |
| **Austral** | https://github.com/austral/austral · https://austral-lang.org/spec/spec.html | 1,587★, Apache-2.0, pushed 2025-07-29 | capability-based security in the language | linear types for beginners (OPINION: too hard) |
| **Deno permissions** | https://docs.deno.com/runtime/fundamentals/security/ · https://github.com/denoland/deno | 108,717★, MIT | deny-by-default runtime permissions, `--allow-*` flags → **`--allow` / `--deny` host policy** | process-wide (ambient) grants |
| **Hedy** | https://github.com/hedyorg/hedy · https://hedy.org/research/Hedy_A_Gradual_Language_for_Programming_Education_2020.pdf | 1,694★, EUPL-1.2 | gradual surface; **localised keyword sets** as lexer-only dialects (v1) | fixed, non-extensible levels |
| **Elm** error messages | https://elm-lang.org/news/compiler-errors-for-humans · https://github.com/elm/compiler | 7,913★, BSD-3-Clause | human-first diagnostics → **5-part errors** | — |
| **Gleam** | https://gleam.run/ · https://github.com/gleam-lang/gleam | 21,983★, Apache-2.0 | friendly errors; **formatter as part of the language**; "one way to do it" | no macros (less hackable by design) |
| **Trio** | https://trio.readthedocs.io/en/stable/reference-core.html · https://github.com/python-trio/trio | 7,347★ | nurseries and cancel scopes → **`together:`, `within`** | — |
| **Kotlin coroutines** | https://kotlinlang.org/docs/coroutines-basics.html | (docs) | parent waits for children; recursive cancellation | — |
| **Java StructuredTaskScope** | https://openjdk.org/jeps/525 | preview API (JEP 525 delivered in JDK 26) | "first success wins" race → **`first of:` (D4)** | preview churn |
| **Python TaskGroup / PEP 654** | https://peps.python.org/pep-0654/ | TaskGroup added in Python 3.11 | aggregated failures → **`several`** (but single failure unwrapped, D6) | always-wrap |
| **Go channels** | https://go.dev/ref/spec | spec | unbuffered rendezvous; panic on send-to-closed/double close | zero value from a closed channel (Sayform returns `nothing`) |
| **Lua** indexing | https://www.lua.org/pil/11.1.html · https://github.com/lua/lua | 10,363★ | **1-based indexing** precedent | — |
| **Julia** | https://docs.julialang.org/en/v1/manual/noteworthy-differences/ · https://docs.julialang.org/en/v1/manual/methods/ · https://github.com/JuliaLang/julia | 49,194★, MIT | 1-based inclusive slices; **multiple dispatch** for operators | call-time ambiguity errors (Sayform reports at definition) |
| **Dijkstra EWD 831** | https://www.cs.utexas.edu/~EWD/transcriptions/EWD08xx/EWD831.html | essay | the half-open range argument → kept as `a..<b` | 0-based default (D1 chose 1-based) |
| **Wolfram Language** rules | https://reference.wolfram.com/language/tutorial/PatternsAndTransformationRules.html | proprietary | **patterns and transformation rules** as everyday code | global, order-dependent rules (Sayform: scoped rulesets, saturation) |
| **Lisp homoiconicity** | McCarthy 1960: https://www-formal.stanford.edu/jmc/recursive.pdf · R7RS quasiquote: https://small.r7rs.org/attachment/r7rs.pdf | papers | **code as data**; quasiquote/unquote → `quote (…)` and `~e` | S-expression syntax |
| **Inform 7** | https://github.com/ganelson/inform · https://ganelson.github.io/inform-website/ | 1,651★, Artistic-2.0 | prose readability; rulebooks | free-form English that invites guessing |
| **AppleScript** (lesson) | Cook, HOPL III 2007: https://www.cs.utexas.edu/~wcook/Drafts/2006/ashopl.pdf | paper | the warning: "easy to read … more difficult to write"; per-app terms collide | **natural-language guessing** → closed grammar, symbol twin for every phrase, ambiguity = error |
| **Swift** SE-0304 | https://github.com/swiftlang/swift-evolution/blob/main/proposals/0304-structured-concurrency.md | repo 15,882★; proposal status "Implemented (Swift 5.5)" | task groups, cooperative cancellation checkpoints | — |
| **COBOL** (lineage) | — (no single canonical source; OPINION from common knowledge) | n/a | exact decimal arithmetic for business values → **exact decimals by default** | verbosity, global state |
| **Quorum** (Stefik) | evidence via Stefik & Siebert 2013 (below) | repository UNKNOWN | keyword choices tested empirically → closed, evidence-led keyword set | — |
| **Mojo** | https://github.com/modular/modular | 29,934★, licence NOASSERTION | Python surface over a systems core (validates "Python-shaped" reach) | performance-first focus; mixed licensing |
| **OpenXTalk-Beyond** (HyperTalk lineage) | https://github.com/SethMorrowSoftware/OpenXTalk-Beyond | 2★, GPL-3.0, pushed 2026-10-10 | possessive chains (`the name of …`) read well → `the f of x` | free-form English |
| **plain-lang**, **englang** (recent English-like languages) | https://github.com/StudioPlatforms/plain-lang · https://github.com/Prasundas99/englang | 37★ (pushed 2025-09-06) · 15★ | confirm the niche is open | no traction (FACT) |
| **Nim** | https://github.com/nim-lang/Nim | 18,261★ | Python-like indentation; effect tracking | invisible macro scope |
| **SymPy** | https://github.com/sympy/sympy | 14,995★ | pragmatic symbolic maths | `==` overloading confusion; symbols as second-class |
| **Python** `doctest`, `fractions`, `decimal` | https://docs.python.org/3/library/doctest.html · https://docs.python.org/3/library/fractions.html · https://docs.python.org/3/library/decimal.html | stdlib | **examples in notes are tests**; exact rationals and decimals for the v0 host | — |
| **F# units of measure** | https://learn.microsoft.com/en-us/dotnet/fsharp/language-reference/units-of-measure | docs | units in types → dialect `units` | — |
| **Rust** orphan rule and editions | https://doc.rust-lang.org/reference/items/implementations.html · https://doc.rust-lang.org/edition-guide/editions/index.html | docs | coherence (**orphan rule**); **editions** over a shared core | — |
| **BLAKE3** | https://github.com/BLAKE3-team/BLAKE3 · https://c2sp.org/BLAKE3 · https://datatracker.ietf.org/doc/html/draft-aumasson-blake3 | 6,468★, Apache-2.0; PyPI `blake3` 1.0.11 | core hash algorithm | — |
| **Lark** | https://github.com/lark-parser/lark · https://lark-parser.readthedocs.io/en/stable/ | 6,005★, MIT; PyPI `lark` 1.3.1 | v0 parser (with `Indenter`) | — |
| **Hypothesis** | https://github.com/HypothesisWorks/hypothesis · https://hypothesis.readthedocs.io/en/latest/ | 9,071★, PyPI 6.168.5 (MPL-2.0) | property-based round-trip tests (dev only) | — |
| **Black** | https://black.readthedocs.io/en/stable/the_black_code_style/current_style.html · https://github.com/psf/black | 41,886★ | 88-column default line width | — |
| **Unicode** UAX #15, #29, #31, UTS #39 | https://www.unicode.org/reports/tr15/ · https://www.unicode.org/reports/tr29/ · https://www.unicode.org/reports/tr31/ · https://www.unicode.org/reports/tr39/ · https://www.unicode.org/versions/Unicode15.1.0/ | standards | NFC names, grapheme clusters, identifier classes, confusables | — |
| **atHome** (Adam's spine) | https://github.com/ao3575911/atHome | 0★, AGPL-3.0, pushed 2026-05-14 | capability tokens (audience, expiry, revoke) as an **optional host adapter** | linking AGPL code into the Apache-2.0 core |

Evidence for needs N1–N3 (FACT, carried from the seed and re-checked for availability): Stack Overflow 2025 AI survey https://survey.stackoverflow.co/2025/ai/ · METR 2025 study https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/ · Sonatype 2026 malware report https://www.sonatype.com/state-of-the-software-supply-chain/2026/open-source-malware · Stefik & Siebert 2013 https://dl.acm.org/doi/10.1145/2534973 (ACM returns 403 to scripted fetches; cited from the seed's earlier check).

## 2. What is new (honest)
Nothing below is a first in isolation. The **combination** was not found in the 10 Oct 2026 searches (`gh search` for English-like languages created since 2025 returned 57 repositories, top 37★; none combines these; general claim UNKNOWN beyond that search).
| # | Feature | Status |
|---|---|---|
| I1 | Plain-English effects (`needs network limited to "x"`) checked statically **and** enforced by capabilities, optionally token-backed | remix |
| I2 | Two surfaces (words ⇄ symbols) with a **tested round-trip law** over one core | remix; guaranteed law across two surfaces is uncommon (OPINION) |
| I3 | `explain` as a **language guarantee** (law L7) for reviewing generated code | probably first as a normative guarantee (OPINION) |
| I4 | Scoped rewrite rules and e-graph simplification in the core of a Python-shaped language | remix (OPINION) |
| I5 | Exact numbers by default, money/units as dialects | remix |
| I6 | Content-addressed definitions over a core shared by several surfaces | small new idea |
| I7 | Dialects per module with conflicts as errors | remix |
| I8 | Error messages as a normative conformance suite (5 parts, stable codes, one test per code) | remix |
| I9 | Lockfile that pins **semantic hashes and capability rows**, failing CI when a dependency's authority grows | remix of lockfiles + capabilities (OPINION) |

## 3. Name check (FACT, 10 Oct 2026)
`sayform`: PyPI 404, npm 404, `github.com/ao3575911/sayform` 404 (free). Trademark and domain: UNKNOWN.
