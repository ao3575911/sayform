# 04 · Core AST, lowering, round-trip laws, canonical serialisation and hash (F15)
Spec `0.1-lite` · edition 0 · core version `sayform/core/1`. RFC 2119 keywords as in [01-principles.md](01-principles.md).

## 1. The constitutional rule
Every surface phrasing (words, symbols, mixed, dialect sugar) **lowers** to exactly one core tree. The core **prints** in two canonical surfaces. Parsing either print gives back the same core. The hash is computed over the core.

Notation: `Node(field: Type, …)`; `[T]` list; `T?` optional; `Sym` interned symbol (canonical `-` spelling); `QName` dotted path; `Truth` yes/no. All nodes are **immutable** (the reference implementation uses `@dataclass(frozen=True, slots=True)`). Source spans and trivia live in a **side table keyed by node path** and are excluded from node equality and from the hash.

## 2. Node catalogue: 44 tagged nodes
Tags are permanent, never reused, and new tags arrive only at an edition boundary (F26). **v0 profile** = the 40 nodes not marked *v0.1*. A v0 implementation MUST parse v0.1 constructs and reject them with SAY-E1013 (never with a generic syntax error).

### 2.1 Family M: modules and declarations
| Tag | Node | Fields (catalogue order = serialisation order) | Invariants (error if violated) | Profile |
|---|---|---|---|---|
| 01 | `Module` | `name: QName, edition: Int, uses: [Use], needs: EffectRow, dialects: [QName], body: [Decl]` | name matches file path (E0701); header order fixed (E0702); `edition` required under `strict` (E1012, else W1012, default 0); `needs` ⊇ effects of every definition (E0501) | v0 |
| 02 | `Use` | `path: QName, names: [Sym]?, alias: Sym?, foreign: Sym?` | `foreign ∈ {python, c, wasm}` (v0.1/v1); imported names exist (E0304); unknown module E0304 | v0 (`foreign`: v0.1) |
| 03 | `Func` | `name: Sym, params: [Param], result: Type?, effects: EffectRow, fails: [Sym], generics: [TParam], body: Block` | param names and leads unique (E0407); positional params first (E0407); effects cover body (E0501); `fails` sorted; `Return` values match `result` when typed (E0201) | v0 |
| — | `Param` (structure) | `name: Sym, slot: Sym?, type: Type?, default: Expr?` | `slot ∈ {of, to, from, by, into, for, with}`; `of` only on the first param | v0 |
| — | `TParam` (structure) | `name: Sym, role: QName?` | `role` is v0.1 | v0 |
| 04 | `RecordDef` | `name: Sym, plural: Sym, tparams: [TParam], fields: [Field], invariants: [Expr], changeable: Truth` | field names unique (E0407); invariants pure (E0501); name uppercase (E0126) | v0 |
| — | `Field` (structure) | `name: Sym, type: Type, default: Expr?` | — | v0 |
| 05 | `VariantDef` | `name: Sym, plural: Sym, tparams: [TParam], cases: [Case]` | case names unique, lowercase (E0407, E0126) | v0 |
| — | `Case` (structure) | `name: Sym, fields: [Field]` | — | v0 |
| 06 | `RoleDef` | `name: Sym, tparams: [TParam], requires: [Signature], laws: [Sym]` | signatures mention `Self` | *v0.1* |
| 07 | `Plays` | `type: Type, role: QName, methods: [Func]` | orphan rule (E0403); covers every requirement (E0405) | *v0.1* |
| 08 | `EffectDef` | `name: Sym, narrowings: [Sym]` | no clash with built-in effects (E0404) | *v0.1* |
| 09 | `Ruleset` | `name: Sym, rules: [Rule]` | module-scoped; cannot be exported as global (E0903) | v0 |
| 10 | `Rule` | `lhs: Pattern, rhs: Expr, guard: Expr?` | pattern variables of `rhs` ⊆ those of `lhs` (E0902); guard pure | v0 |
| 11 | `OperatorDef` | `word: Text, symbol: Text?, arity: Int, prec: (relation: Sym, level: Sym), assoc: Sym, means: QName` | only inside `dialect` (E0704); relative precedence (E0406) | *v0.1* |
| 12 | `Check` | `label: Text?, subject: Expr, relation: Sym, expected: Expr?, body: Block?` | `relation ∈ {equals, holds, fails-with, matches, is}`; never inside a function (E1004) | v0 |

### 2.2 Family S: statements
| Tag | Node | Fields | Invariants | Profile |
|---|---|---|---|---|
| 13 | `Bind` | `target: Pattern, value: Expr, mutable: Truth, type: Type?` | no rebinding in same scope (E0301); irrefutable target (E0905) | v0 |
| 14 | `Rebind` | `name: Sym, value: Expr` | `name` bound changeable (E0302) | v0 |
| 15 | `SetField` | `target: Expr, field: Sym, value: Expr` | target type declared changeable (E0303) | v0 |
| 16 | `If` | `branches: [(cond: Expr, body: Block)], else: Block?` | each cond is Truth (E0201 static / E0212 runtime) | v0 |
| 17 | `Match` | `subject: Expr, cases: [(pattern: Pattern, guard: Expr?, body: Block)], else: Block?` | exhaustive or `else` (W0911; E in `strict`); guards pure | v0 |
| 18 | `For` | `binder: Pattern, source: Expr, body: Block` | source iterable (E0201/E0212) | v0 |
| 19 | `While` | `cond: Expr, body: Block` | cond Truth | v0 |
| 20 | `Stop` | — | inside For/While (E0130) | v0 |
| 21 | `Skip` | — | inside For/While (E0130) | v0 |
| 22 | `Return` | `value: Expr?` | inside Func (E0130) | v0 |
| 23 | `ExprStmt` | `expr: Expr` | discarding a `may fail` result is W0201 | v0 |
| 24 | `WithCap` | `cap: Expr, narrowing: [Narrow], body: Block` | edition 0: `cap` is `Name` of a built-in effect; narrowed ⊆ parent (E0504); revoked at block exit | v0 |
| — | `Narrow` (structure) | `kind: Sym, arg: Expr?` | `kind ∈ {limited-to, read-only}` | v0 |
| 25 | `Concurrent` | `mode: Sym, children: [Child]` | `mode ∈ {together, all, first}`; `together` children are blocks of statements; `all`/`first` children are expressions and the node is valid as the whole value of `Bind`/`Rebind`/`Return`/`ExprStmt` only; no `Bind` directly in a `together` child (E0604); needs `tasks` (E0601) | v0 |
| — | `Child` (structure) | `label: Sym?, body: Expr \| Block` | labels unique | v0 |
| 26 | `Within` | `limit: Expr, body: Block` | `limit` is a time quantity (E0605); needs `tasks` (E0601) | v0 |
| 27 | `Block` | `stmts: [Stmt]` | non-empty (use `nothing` as a placeholder statement) | v0 |

### 2.3 Family E: expressions
| Tag | Node | Fields | Invariants | Profile |
|---|---|---|---|---|
| 28 | `Lit` | `kind: Sym, value` | `kind ∈ {integer, rational, decimal, approx, text, truth, nothing, money, quantity}`; integers ≥ 0 from source; rational never produced by source (only by `simplify`/`evaluate` results inside Expression values); decimals keep written scale; `money`/`quantity` only from dialects (time quantities are core) | v0 |
| 29 | `Interp` | `parts: [Text \| Expr]` | adjacent text parts merged; no empty text parts | v0 |
| 30 | `SymLit` | `name: Sym` | — | v0 |
| 31 | `Name` | `name: Sym, ref: Ref` | `ref ∈ Local(i) \| Def(hash) \| Builtin(sym) \| Foreign(path) \| PatVar(i) \| SCC(i)`, filled by resolution; unresolved is E0304 | v0 |
| 32 | `Get` | `target: Expr, field: Sym, optional: Truth` | field exists when typed (E0206), else runtime problem `no-such-field` | v0 |
| 33 | `Index` | `target: Expr, index: Expr, optional: Truth` | lists 1-based; literal `0` is E0181; runtime 0 panics E0831; out of range panics E0832 unless optional | v0 |
| 34 | `Call` | `fn: Expr, args: [Expr], slots: [(Sym, Expr)]` | slots in the callee's declared order when `fn` resolves to `Def`/`Builtin`, otherwise by code point order of slot name; operators lower here | v0 |
| 35 | `Lambda` | `params: [Param], body: Expr` | zero-parameter lambdas are thunks; edition 0 bodies are expressions only | v0 |
| 36 | `ListLit` | `items: [Expr]` | — | v0 |
| 37 | `MapLit` | `pairs: [(Expr, Expr)]` | duplicate literal keys E0821 | v0 |
| 38 | `SetLit` | `items: [Expr]` | non-empty (`empty-set` is a prelude constant); duplicate literal items E0821 | v0 |
| 39 | `RecordLit` | `type: Type, fields: [(Sym, Expr)], base: Expr?` | fields in declaration order; missing field without default E0211 | v0 |
| 40 | `TypeTest` | `value: Expr, type: Type` | — | v0 |
| 41 | `Try` | `expr: Expr` | enclosing Func `fails` covers the kinds (E0207) | v0 |
| 42 | `Quote` | `expr: Expr` | — | v0 |
| 43 | `Unquote` | `expr: Expr` | only inside `Quote` (E0901) | v0 |
| 44 | `TypeExpr` | `type: Type` | — | v0 |

### 2.4 Sub-nodes (tagged because they appear in union-typed fields)
**Types (tags 60–68, 9 nodes):** 60 `TName(ref)` · 61 `TApply(head, args)` · 62 `TOptional(type)` · 63 `TUnion(types)` (sorted by SCS-1 bytes, flattened, deduplicated) · 64 `TVar(name)` · 65 `TFunc(params, result, effects, fails)` · 66 `TQuantity(dimension)` · 67 `TMoney(currency?)` · 68 `TAnything`.

**Patterns (tags 70–78, 9 nodes):** 70 `PBind(name, type?)` · 71 `PWild` · 72 `PLit(lit)` · 73 `PRecord(type, fields: [(Sym, Pattern)], open: Truth)` · 74 `PCase(case: Sym, fields: [(Sym, Pattern)], open: Truth)` · 75 `PList(prefix: [Pattern], rest: Pattern?)` · 76 `PRange(lo, hi, inclusive)` · 77 `PAlt(alts)` · 78 `PQuote(expr)` (pattern variables inside are `Name` with `ref = PatVar(i)`).

Structures (`Param`, `TParam`, `Field`, `Case`, `Narrow`, `Child`, branch/case tuples, slot pairs, `EffectRow`) have no tag: they are always in a field of known type and are encoded as their fields in order.

`EffectRow` = sorted list of `(effect: Sym, narrowing: [Narrow])`.

## 3. Lowering table (every surface construct → core)
Operators lower to `Call(Name(op, Builtin(op)), …)`. The printer recognises each builtin callee and prints its operator form, so `add(a, b)` and `a + b` are **one core** and both print `a + b` / `a plus b`.

| Surface (words · symbols) | Core |
|---|---|
| module header lines | `Module` (01) |
| `use p: a, b as x` | `Use` (02) |
| `to f … :` · `def f(…):` | `Func` (03) |
| `a Person has …` · `record Person(…)` | `RecordDef` (04) |
| `a Shape is one of:` · `variant Shape:` | `VariantDef` (05) |
| `role R:` | `RoleDef` (06, v0.1) |
| `T plays R:` | `Plays` (07, v0.1) |
| `effect payments` | `EffectDef` (08, v0.1) |
| `ruleset r:` | `Ruleset` (09) |
| `rewrite L as R [when G]` · `L => R [if G]` | `Rule` (10) |
| `operator "dot" …` | `OperatorDef` (11, v0.1) |
| `check that a equals b` · `check a = b` | `Check(subject=a, relation=equals, expected=b)` (12) |
| `check that e` · `check e` (other Truth) | `Check(e, holds)` |
| `check that e is P` | `Check(e, is, TypeExpr/predicate)` |
| `check that e fails with k` · `check e fails k` | `Check(e, fails-with, SymLit k)` |
| `check that e matches P` | `Check(e, matches, Quote P)` |
| `check "label":` block | `Check(label, body=Block)` |
| `let x be E` · `let x = E` | `Bind(PBind x, E, mutable=no)` (13) |
| `let x be E, changeable` · `var x = E` | `Bind(PBind x, E, mutable=yes)` |
| `set x to E` · `x := E` | `Rebind(x, E)` (14) |
| `add E to x` · `x += E` | `Rebind(x, Call(added, [x, E]))` |
| `change the f of p to E` · `p.f := E` | `SetField(p, f, E)` (15) |
| `if/otherwise if/otherwise` · `if/elif/else` | `If` (16) |
| `match … when … / case …` | `Match` (17) |
| `for each x in xs:` · `for x in xs:` | `For(PBind x, xs, body)` (18) |
| `for each x received from ch:` · `for x in received(ch):` | `For(PBind x, Call(received, [ch]), body)` |
| `repeat n times:` | `For(PWild, Call(range, [1, n]), body)`; words print `repeat n times` whenever binder is `PWild`, range start is literal `1`, inclusive, no step; symbols print `for _ in 1..n:` |
| `while c:` | `While` (19) |
| `stop` · `break` | `Stop` (20) |
| `skip` · `continue` | `Skip` (21) |
| `give back E` · `return E` | `Return` (22) |
| any expression as a statement | `ExprStmt` (23) |
| `with network limited to "h"[, read only]:` | `WithCap(Name network, [Narrow(limited-to, "h")(, Narrow(read-only))], body)` (24) |
| `together:` · `all of:` / `all_of:` · `first of:` / `first_of:` | `Concurrent(together\|all\|first, …)` (25) |
| `within 5 seconds:` · `within 5s:` | `Within` (26) |
| indented block | `Block` (27) |
| `12.50`, `7`, `"x"`, `yes`/`true`, `no`/`false`, `nothing`, `5 seconds`, `approx 0.1` | `Lit` (28) |
| `"Hi {name}"` | `Interp` (29) |
| `the symbol x` · `'x` | `SymLit` (30) |
| a name | `Name` (31) |
| `p's f` · `the f of p` · `p.f` / `…, if any` · `p?.f` | `Get(p, f, optional=no\|yes)` (32) |
| `item i of c` · `c[i]` / `…, if any` · `c?[i]` | `Index(c, i, optional=no\|yes)` (33) |
| `f x`, `f of x`, `f(x)`, slots, named args, `a then f`, `a \|> f` | `Call` (34) |
| `given x, E` · `x => E` | `Lambda` (35) |
| `[a, b]` | `ListLit` (36) |
| `{k: v}` · `{}` | `MapLit` (37) |
| `{a, b}` | `SetLit` (38) |
| `Person with name "Ada"` · `Person(name="Ada")`; `p with age 37` · `p.with(age=37)` | `RecordLit` (39) |
| `x is a number` · `x is Number`; `x is nothing` | `TypeTest` (40) |
| `try E` · `E?` | `Try` (41) |
| `quote (E)` · `` `(E) `` | `Quote` (42) |
| `~e` | `Unquote` (43) |
| `the type a list of numbers` · `List[Number]` | `TypeExpr` (44) |
| `a plus b` · `+`; `minus` · `-`; `times` · `*`; `divided by` · `/`; `divided by …, rounded down` · `//`; `mod` · `%`; `to the power of` · `^`; `negative` · unary `-` | `Call(add\|subtract\|multiply\|divide\|floor-divide\|modulo\|power\|negate, …)` |
| `a equals b` · `=` / `==` | `Call(equal, [a, b])` |
| `a is not equal to b` · `!=` / `≠` | `Call(not, [Call(equal, [a, b])])` |
| `is less than` `<` · `is at most` `<=` · `is greater than` `>` · `is at least` `>=` | `less` · `less-eq` · `greater` · `greater-eq` |
| `lo < x < hi` (and `<=`, `>`, `>=` variants, R14) · `x is between lo and hi[, exclusive[ above\|below]]` | `Call(between, [x, lo, hi], slots=[(low-inclusive, …), (high-inclusive, …)])` (a slot is present only when it is `no`) |
| `not a` · `!a` | `Call(not, [a])` |
| `a and b` · `&&`; `a or b` · `\|\|` | `Call(and, [a, Lambda([], b)])` · `Call(or, [a, Lambda([], b)])` |
| `x is in c` · `c contains x` · `x in c` · `∈` | `Call(contains, [c, x])` |
| `a is the same as b` · `===` | `Call(same, [a, b])` |
| `x is empty` (adjective) | `Call(is-empty, [x])` |
| `a joined with b` · `a ++ b` | `Call(join, [a, b])` |
| `items joined by s` | `Call(join-all, [items, s])` |
| `c each E` · `each x in c, E` | `Call(map, [c, Lambda([it\|x], E)])` |
| `each x in c at the same time, E` | `Call(map-concurrent, [c, Lambda([x], E)])` |
| `c where cond` | `Call(filter, [c, Lambda([it], cond)])` |
| `c sorted` · `c sorted by k[, descending]` | `Call(sort, [c])` · `Call(sort-by, [c, Lambda([it], k)], slots=[(descending, yes)]?)` |
| `c grouped by k` | `Call(group-by, [c, Lambda([it], k)])` |
| `from a to b [by s]` · `a..b [by s]`; `from a up to b` · `a..<b` | `Call(range, [a, b], slots=[(exclusive, yes)?, (step, s)?])` |
| `a or else b` · `a ?? b` | `Call(default, [a, Lambda([], b)])` |
| `problem k [with …]` | `Call(problem, [SymLit k], slots=…)` |
| `evaluate e [with bindings m]` · `evaluate(e[, bindings=m])` | `Call(evaluate, [e], slots=[(bindings, m)]?)` |
| `simplify e using rs` | `Call(egraph-simplify, [e, Name rs])` |
| `e matches P` · `e ~= P` | `Call(match, [e, Quote P])` (PATVARs inside as `Name(PatVar)`) |
| `a is equivalent to b using rs` · `equivalent(a, b, rs)` · `a ≡ b using rs` | `Call(egraph-equiv, [a, b, Name rs])` |
| `x in feet` (units) | `Call(convert, [x, Lit(quantity unit ft)])` |
| dialect operator `a dot b` · `a · b` | `Call(<means>, [a, b])` (v0.1) |

**Bare field of `it`** (R10) lowers to `Get(Name(it), field, no)`; the words printer prints the bare field name when R10 would parse it back the same way, otherwise `it's field`.

## 4. Round-trip laws
`c` is any well-formed core tree, `s` any accepted source text, `W`/`S` the words/symbols printers, `P` parse+lower (either surface or mixed).
| # | Law | Meaning |
|---|---|---|
| L1 | `P(W(c)) = c` | words print is lossless |
| L2 | `P(S(c)) = c` | symbols print is lossless |
| L3 | `W(P(s)) = fmt_w(s)` and `fmt_w(fmt_w(s)) = fmt_w(s)` (likewise `S`) | print∘parse normalises; formatting is idempotent |
| L4 | `P(W(P(s))) = P(s)` and `P(S(P(s))) = P(s)` | normalising never changes meaning |
| L5 | `hash(P(s)) = hash(P(S(P(s)))) = hash(P(W(P(s))))` | the hash ignores the surface |
| L6 | renaming a local or a function's own top-level name leaves the hash unchanged; renaming a field, slot, case, record/variant type or export changes it | D2, locked |
| L7 | `explain(c)` is total: never throws; every node yields a non-empty sentence | `explain` is a guarantee |
"Equal" means structural core equality ignoring spans. L1 and L2 additionally require that trivia survive (§8). A violation found at run time is SAY-E1001 (internal bug).

**Testing (normative for conformance):** a type-directed generator of well-scoped core trees (depth ≤ 6, width ≤ 5) built on Hypothesis; name pool includes near-keywords (`lett`, `be-ok`, `times-up`) and contextual words used as names (`least`, `back`, `item`); value edge cases `0`, `approx -0.0`, `12.50` vs `12.5`, a 200-digit integer, text containing `{`, `\`, `"""`, emoji with skin-tone modifiers and combining marks, nested quote/unquote. **200 examples per law per PR; 10,000 nightly.** Counterexamples go to `tests/roundtrip/regressions/` and are replayed forever. A **mutation check** (breaking one row of the printer's operator table) MUST make at least one law fail.

## 5. Canonical serialisation SCS-1
| Item | Encoding |
|---|---|
| Header | ASCII `sayform/core/1` + byte `0x00`, then edition (unsigned LEB128) |
| Node | tag byte, then fields in catalogue order; field names never appear |
| Structure | its fields in order, no tag |
| List | unsigned LEB128 count, then items |
| Optional | `0x00` absent · `0x01` then value |
| Truth | `0x00` no · `0x01` yes |
| Sym / Text | NFC UTF-8, unsigned LEB128 byte length prefix; identifiers in canonical `-` form |
| Integer | sign byte (`0x00` +, `0x01` −), LEB128 byte length, big-endian magnitude with no leading zero bytes (zero has length 0) |
| Rational | numerator (Integer), denominator (Integer > 1) |
| Decimal | coefficient (Integer), exponent (Integer), exactly as written: `12.50` → (1250, −2) |
| Approx | IEEE 754 binary64 big-endian; `-0.0` kept; one canonical NaN `0x7FF8000000000000` (only under `ieee`) |
| Money / Quantity | ISO 4217 code text + Decimal · Number + canonical unit symbol text (`ms`, `s`, `min`, dialect units) |
| `Name.ref` | kind byte: `0` Local + LEB128 index (binding order within the enclosing definition) · `1` Def + 32 hash bytes · `2` Builtin + symbol text · `3` Foreign + language, module path, name (texts) · `4` PatVar + LEB128 index (order of first occurrence in the rule or pattern) · `5` SCC + LEB128 index |
| Symbol *names* in `Name` | **omitted** (only `ref` is encoded) |

## 6. The core hash
1. **Algorithm:** BLAKE3, 256-bit output ([BLAKE3](https://github.com/BLAKE3-team/BLAKE3), [C2SP spec](https://c2sp.org/BLAKE3)). Printed as `b3:` + lowercase RFC 4648 base32 without padding (52 characters). UIs show the first 12 characters; lockfiles store the full value.
2. **Definition hash** = BLAKE3(SCS-1 header ‖ serialisation of the definition with its own top-level name omitted).
3. **Included:** structure of every node and literal; types, effects, `fails`, generics, invariants; field, slot, case and record/variant type names; edition and core version; callees through their definition hashes (Merkle).
4. **Excluded:** comments, notes, blank lines, spans, the surface used, which accepted spelling was used, dialect sugar (only its expansion), local names, the function's own name, formatting, `explain` templates.
5. **Recursion:** a strongly connected component of mutually recursive definitions is hashed as one unit (members in order of their SCS-1 bytes with internal references replaced by `SCC(i)`); each member's hash is BLAKE3(component hash ‖ LEB128 i). (OPINION; Unison's exact scheme UNKNOWN here.)
6. **Module hash** = BLAKE3(header ‖ sorted list of `(export name, definition hash)` pairs). Export names count because importers depend on them.
7. **Doc hash** covers notes; **test hash** covers checks plus note examples (F25).
8. A serialiser that meets a tag unknown to its core version MUST stop with SAY-E1002.
9. Why BLAKE3 (OPINION): no variants, fast, incremental (good for LSP re-hashing); the `b3:` prefix allows a future algorithm change. CPython 3.13.5 `hashlib` has no BLAKE3 (FACT), so the reference interpreter depends on PyPI `blake3` (FACT: 1.0.11).

## 7. Determinism requirements
Given the same inputs, edition and core version, `P`, `W`, `S`, `explain`, `hash` and `simplify` MUST be deterministic and MUST NOT depend on hash-table iteration order, wall-clock time, locale or platform.

## 8. Trivia attachment (comments and notes)
1. A `note:` (with its continuation lines) attaches to the next declaration or statement at the same indentation. A note before `Func`, `RecordDef`, `VariantDef` or `RoleDef` is its documentation (LSP hover; `explain` prints "(Note: …)").
2. An own-line `#` comment is leading trivia of the next node at the same indentation; an end-of-line `#` is trailing trivia of that line's statement.
3. A comment at the end of a block with no following node is trailing trivia of the `Block`.
4. A comment inside a bracketed continuation stays with its enclosing statement and keeps its relative line.
5. Trivia is keyed by node path, so reprinting in the other surface keeps every comment beside the same node.
6. A `note:` inside an expression is SAY-E0120.
7. Notes are outside the core hash; they affect the doc hash and, if they contain examples, the test hash.

## 9. Conformance
`AST-01`…`AST-44` (one per tag), `AST-T60`…`AST-T68`, `AST-P70`…`AST-P78`, `LOW-01`…`LOW-60` (one per lowering row), `RT-L1`…`RT-L7`, `HASH-01`…`HASH-12` in [15-conformance.md](15-conformance.md).
