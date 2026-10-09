# Sayform specification — `spec 0.1-lite`
**Status:** frozen for v0 implementation · edition 0 · core version `sayform/core/1` · Sat 10 Oct 2026 (AWST) · owner Adam ([ao3575911](https://github.com/ao3575911)).
Language **Sayform** · files `.say` · CLI `say` · repository name `sayform`.

Sayform is a small, Python-shaped language whose programs have **one canonical core** that prints both as plain English (words) and as compact symbols, whose functions **declare what they may touch** (enforced as capabilities), and whose **expressions are data** (quote, scoped rewrite rules, simplification). This folder is the single source of truth for implementations. It consolidates the seed spec and the F15-onwards spec, then applies a **lite pass** (strip to the smallest core that keeps every law) and a **harden pass** (RFC 2119 wording, no ambiguity, an error path and a test for every operator and node, cross-file consistency).

## Reading order
| # | File | What it fixes |
|---|---|---|
| 1 | [01-principles.md](01-principles.md) | needs N1–N7, the 7 design laws, hard budgets |
| 2 | [02-lexical.md](02-lexical.md) | characters with code points, words, literals, **63 reserved + 89 contextual words** |
| 3 | [03-grammar.md](03-grammar.md) + [03-grammar.ebnf](03-grammar.ebnf) | both surfaces, precedence ladder, disambiguation rules R1–R20 |
| 4 | [04-core-ast.md](04-core-ast.md) | 44-node catalogue, lowering table, round-trip laws, SCS-1, BLAKE3 hash |
| 5 | [05-types-values.md](05-types-values.md) | types, numbers, text, records, collections, equality |
| 6 | [06-operators.md](06-operators.md) | every operator with function, types, edge cases, errors, test ID |
| 7 | [07-semantics.md](07-semantics.md) | evaluation, binding, functions, control flow, patterns, errors, dispatch |
| 8 | [08-symbolic.md](08-symbolic.md) | symbols, quote/unquote, evaluate, rulesets, simplify, equivalence |
| 9 | [09-effects-capabilities.md](09-effects-capabilities.md) | effects, capability context, host policy, atHome adapter, security model |
| 10 | [10-modules-dialects.md](10-modules-dialects.md) | modules, dialects, editions, packages, lockfile |
| 11 | [11-concurrency.md](11-concurrency.md) | structured concurrency, channels, scheduler |
| 12 | [12-stdlib.md](12-stdlib.md) | the 74 v0 builtins with signatures |
| 13 | [13-tooling.md](13-tooling.md) | `say` CLI, formatter rules, `explain`, REPL, tests-as-syntax, Python bridge |
| 14 | [14-errors.md](14-errors.md) | 96 error codes with 5-part message templates |
| 15 | [15-conformance.md](15-conformance.md) | named conformance tests and golden programs |
| 16 | [16-prior-art.md](16-prior-art.md) | what is recycled from whom (live-verified links) and what is new |
| 17 | [17-roadmap-kill.md](17-roadmap-kill.md) | v0 / v0.1 / v1 and kill criteria |
| — | [OPEN.md](OPEN.md) | the 5 genuinely open items |
| — | [CHANGELOG.md](CHANGELOG.md) | every cut and tightening vs the source docs (⚑ = changed a source decision; all accepted by Adam 2026-10-10) |
| — | [TRACE.md](TRACE.md) | every source section → destination file |

## Locked decisions (Adam, 10 Oct 2026)
| # | Decision | Where |
|---|---|---|
| D1 | Lists are **1-based in both surfaces**; literal `xs[0]` is SAY-E0181 | 05 §6 |
| D2 | The hash ignores local names and the function's own name; it includes field, slot, case, type and export names | 04 §6 |
| D3 | `-` and `_` in identifiers are the same name; words print `-`, symbols print `_` | 02 §4.1 |
| D4 | `first of:` means first **success**; the rest are cancelled | 11 §2 |
| D5 | **63 reserved words** + a closed contextual list; `show` is a function | 02 §5–§6 |
| D6 | One concurrent problem passes through unwrapped; two or more become `several` | 11 §4 |

## Hard budgets (edition 0, Law 5)
| Item | Value |
|---|---|
| Reserved words | 63 |
| Contextual words | 89 |
| Core nodes (catalogue / v0 profile) | 44 / 40 |
| Type / pattern sub-nodes | 9 / 9 |
| Precedence levels | 16 (P0–P15, P13 reserved) |
| v0 builtins | 74 (53 host + 21 in Sayform) |
| Built-in effects | 9 |
| Error codes | 96 active (1 retired) |
| v0 runtime dependencies | 2 (`lark`, `blake3`); dev `pytest`, `hypothesis`; optional `egglog` |
| Non-ASCII characters required | 0 |

## Hello, world
```say
to main, needs console:
    show "Hello, world"
```
```say
def main() needs console:
    show("Hello, world")
```
Same core, same hash. `say explain` reads it back in English, e.g. ``Function `main`: takes nothing; gives nothing; may use console.`` (full normative output: [15-conformance.md](15-conformance.md) G-01).

## Conventions
RFC 2119 / RFC 8174 key words · **FACT** = checked live 10 Oct 2026 · **OPINION** = design judgement · **UNKNOWN** = not verified · times in AWST (UTC+8).
