# 05 · Types and values (F2, F12, F13, F14, F17, F18, F21)
Spec `0.1-lite` · edition 0. RFC 2119 keywords as in [01-principles.md](01-principles.md).

## 1. Value types (F2)
| Type (symbols) | Words | Values | Notes |
|---|---|---|---|
| `Nothing` | `nothing` | `nothing` | the only value of its type |
| `Truth` | `a truth` | `yes`, `no` | `true`/`false` are input aliases |
| `Number` | `a number` | union of the exact numbers and `Approx` | |
| `Integer` | `an integer` | arbitrary precision, no overflow | exact |
| `Decimal` | `a decimal` | coefficient × 10^exponent, scale kept | exact; every Integer is also a Decimal for type tests |
| `Rational` | `a rational` | reduced p/q, q > 0 | exact; every exact number is a Rational for type tests |
| `Approx` | `an approx` | IEEE 754 binary64 | disjoint from the exact numbers |
| `Text` | `text` | immutable sequence of extended grapheme clusters | §4 |
| `Symbol` | `a symbol` | interned name | compares by name |
| `List[T]` | `a list of Ts` | immutable persistent sequence | 1-based (§6) |
| `Map[K, V]` | `a map from Ks to Vs` | immutable persistent, insertion-ordered | equality ignores order |
| `Set[T]` | `a set of Ts` | immutable persistent, insertion-ordered | equality ignores order |
| record / variant types | `a Person` | nominal | §5 |
| `(A) -> B needs E` | `a function from A to B, needs E` | closures and builtins | |
| `Expression` | `an expression` | an immutable expression-family core tree | [08-symbolic.md](08-symbolic.md) |
| `Problem` | `a problem` | `problem(kind: Symbol, message: Text, data: Map)` | recoverable error value ([07-semantics.md](07-semantics.md) §6) |
| `Channel[T]` | `a channel of Ts` | [11-concurrency.md](11-concurrency.md) | |
| `Type` | `a type` | type values (`TypeExpr`) | |
| `Capability` | `a capability` | unforgeable; not constructible by user code in edition 0 | [09-effects-capabilities.md](09-effects-capabilities.md) |
| `Quantity[dim]` | `a quantity of DIM` | number + unit | core supports only `time`; other dimensions need `dialect units` |
| `Money[CCY]` | `money` / `money in AUD` | Decimal + ISO 4217 currency | `dialect money` |
| `Anything` | `anything` | top type | default for missing annotations |

`T?` / `a T or nothing` = `TOptional(T)`; `A | B` / `an A or a B` = `TUnion`. A fallible function's result type is its declared result plus the problems listed in `may fail with`.

### 1.1 Gradual typing
1. A missing annotation means `Anything`, checked dynamically. Every primitive checks its argument types at run time and panics with SAY-E0212 on a mismatch.
2. A v0 implementation MUST perform these **static** checks: name resolution (E0304), reserved/contextual word rules, call shape against known signatures (E0408–E0410), effect declarations (E0501), `try` coverage (E0207), literal type errors that need no inference (`"a" + 1`, E0202), record construction fields (E0211), pattern rules (E0904, E0905).
3. Full local type inference (E0201 for inferred mismatches, E0208 variance) is a **v1** feature. `dialect strict` requires annotations on every exported function (E0205).

## 2. Type phrases in words (F2, F21)
1. Built-in type words are lowercase in words (`a number`, `text`); user types keep their capital (`a Person`).
2. Articles follow F-R6: `an` before a vowel letter (a e i o u), else `a`, with the closed exception table `a unit`, `a user`, `a URL`, `a UUID`, `an hour`, `an SMS`, `an HTTP…`, `an MCP…` (edition 0; users cannot extend it).
3. **Plurals** after `list of`, `set of`, `map from … to …`, `channel of`: built-in plurals in [03-grammar.md](03-grammar.md) §2; a user type's plural is `(plural WORD)` if declared, else lowercase name + `s`, or + `es` after s, x, z, ch, sh. `text`, `money` and `anything` are mass nouns. Type variables are never pluralised: `a list of T`.
4. Generics: `, for any T [and U] [that plays R]` on functions (`plays` v0.1); `a Pair of A and B has …` on records. Call sites never write type arguments in words; symbols MAY write `largest[Number](xs)`.
5. Variance (v1): immutable collections covariant; function parameters contravariant, results covariant; changeable records invariant (E0208).
6. Higher-kinded types are out of scope for v1.

## 3. Numbers (F13)
### 3.1 Exact by default
1. Integer literals are exact Integers; `0.1` is an exact Decimal; `0.1 + 0.2 equals 0.3` is `yes`.
2. **Result kind rules** (exact operands):
   - `+ - *` on Integer/Decimal operands → Integer if both are Integers, else Decimal. Scale: `+`/`-` → max of the operand scales; `*` → sum of scales.
   - Any operation involving a non-decimal Rational, and every `/`, produces an exact value **normalised** as: Integer if whole; else Decimal if the reduced denominator has no prime factors other than 2 and 5 (scale = the smallest scale that represents it exactly); else Rational. So `1 / 4` is `0.25` and `1 / 3` is `1/3`.
   - `//` rounds toward negative infinity and returns an Integer. `mod` follows the divisor's sign (`-7 mod 3` is `2`).
   - `^` with an Integer exponent is exact (`2 ^ -1` is `0.5`; `0 ^ 0` is `1`). A non-Integer exponent gives an `Approx` result, except when the base is negative, which panics (SAY-E0842).
3. Division, floor division or modulo by exact zero **panics** with SAY-E0841. Use `checked-divide a by b` (may fail with `division-by-zero`) when zero is an expected input.
4. Exact equality is by value: `1 equals 1.0` and `12.50 equals 12.5` are `yes`; scale is a printing property only.
5. `round x with places n` rounds half-even by default; `with mode 'half-up` is the only other edition 0 mode.

### 3.2 Approx
1. `approx 0.1` is binary64. Any operation with an `Approx` operand returns `Approx`. `explain`, `show` and the REPL mark such values `approx` (`approx 0.30000000000000004`).
2. Equality between exact and approx compares exact values (`0.1 equals approx 0.1` is `no`).
3. Approx division by zero, overflow and invalid operations **panic** (SAY-E0841 / E0212) unless `dialect ieee` is active, in which case IEEE 754 infinities and NaN are produced and `nan equals nan` is `no` (FACT: this follows IEEE 754 comparison semantics; standard text is paywalled, so only behaviour is cited).
4. Using an approx value where only exact numbers are allowed (money, indexes, range bounds, `times` count) is SAY-E0801.

### 3.3 Dialect `money` (optional)
1. Literals: `12.50 AUD` (number, space, ISO 4217 code from the dialect's table) and the prefixes `A$`, `US$`, `NZ$`, `€` (U+20AC), `£` (U+00A3). Value `Money(Decimal, Currency)`.
2. `+`/`-` require the same currency (SAY-E0204 static when known, else runtime problem `currency-mismatch` for `checked-add`, panic E0212 for `+`). `Money * Number` → Money; `Money * Money` is SAY-E0201.
3. Conversion requires an explicit rate: `convert price to 'USD with rate r`; rounding is explicit: `round m with places 2` (half-even).
4. Words print `12.50 AUD`; symbols print `A$12.50` when a registered prefix exists.

### 3.4 Dialect `units` (optional)
1. Literals: `5 metres`, `20 cm`, `5m`; value `Quantity(Number, Unit)` with rational conversion factors.
2. `+`/`-` require the same dimension (SAY-E0203); the left operand's unit wins (`5 metres plus 20 cm` is `5.2 metres`). `*` and `/` combine dimensions.
3. `x in feet` converts (R9).
4. The core supports only the time dimension (`ms`, `s`, `min`), so `within 5 seconds` needs no dialect.

### 3.5 Dialect `ieee` (optional)
Enables infinities, NaN and signed zero semantics for `Approx` only. Exact numbers are unaffected.

## 4. Text (F14)
1. Text is an immutable sequence of **extended grapheme clusters** per [UAX #29](https://www.unicode.org/reports/tr29/), Unicode 15.1.0 tables.
2. `length of t` counts grapheme clusters; `code-points of t` and `utf8-bytes of t` are explicit.
3. Comparison (`<`, sorting) is by code point sequence. Locale collation is not in edition 0.
4. No implicit Number→Text conversion except inside interpolation (`display`). `"a" + 1` is SAY-E0202; `"a" ++ 1` is SAY-E0202 with the hint `"a{1}"`.
5. Indexing text is not defined in edition 0 (use `code-points of t` or `split`); `item 1 of t` is SAY-E0201.

## 5. Records and variants (F17)
1. `a NAME has FIELDS.` declares an immutable nominal record; `(plural WORD)`, `, changeable` and `, where INVARIANT` are optional. Block form `has:` with one field per line is the same core (the formatter picks inline when it fits in 88 columns).
2. Variants: `a NAME is one of:` with one `case [with FIELDS]` line per case.
3. Construction: `Person with name "Ada" and age 36` / `Person(name="Ada", age=36)`. Missing fields without defaults: SAY-E0211.
4. Copy with changes: `p with age 37` / `p.with(age=37)`; never mutates.
5. Equality is structural and includes the type name. Field order is declaration order (printing, hashing, `display`).
6. Invariants run on every construction and copy; a failure returns `problem(invalid, field, rule)`, so construction of a record with invariants `may fail with invalid` (and needs `try` or `or else`).
7. `changeable` records allow `change the f of p to E`. A changeable record cannot be sent on a channel or captured by a child task (E0602, E0603).
8. Anonymous records (from labelled `all of:`) are structurally typed and MUST NOT be exported (SAY-E0201 at the export).
```say
a Person (plural people) has a name (text) and an age (an integer, default 0), where age is at least 0
a Shape is one of:
    circle with a radius (a number)
    rectangle with a width (a number) and a height (a number)
```

## 6. Collections and indexing (F18, D1 locked)
1. `List`, `Set`, `Map` are immutable persistent values. Sets and maps iterate and print in insertion order; equality ignores order.
2. Edition 0 has no in-place mutable collection. `add item to cart` rebinds a changeable binding with `added` (lists append, sets insert, maps merge a `{k: v}`).
3. Literals: `[…]`, `{k: v}`, `{}` (empty map), `{a, b}` (non-empty set), `empty-set`.
4. **Indexing is 1-based in both surfaces.** `xs[1]` / `item 1 of xs` is the first item; `xs[-1]` the last; `xs[2..4]` is inclusive; `xs[2..<4]` half-open.
5. A literal `xs[0]` is SAY-E0181 ("Sayform counts from 1; the first item is `xs[1]` or `first of xs`"). A runtime 0 panics SAY-E0831. Out of range panics SAY-E0832; `xs?[i]` / `item i of xs, if any` returns `T or nothing`.
6. `m[k]` on a map looks up key `k` (no 1-based rule); a missing key panics SAY-E0832; `m?[k]` returns `nothing`.
7. Python objects keep their own indexing through `foreign-item` (v0.1, [13-tooling.md](13-tooling.md) §6).
8. Implementation note (OPINION): a persistent vector/HAMT gives O(log n) updates; the v0 reference interpreter MAY use tuples and `dict` copies (O(n)) because it is a reference, not a performance target.

## 7. Equality and identity (F12)
| Operation | Words | Symbols | Core | Rule |
|---|---|---|---|---|
| structural equality | `a equals b` | `a = b` (`==` accepted) | `equal` | defined for all values; functions compare by identity; Expressions compare structurally |
| inequality | `a is not equal to b` | `a != b` | `not(equal)` | |
| identity | `a is the same as b` | `a === b` | `same` | for immutable values `same` MAY return `yes` whenever `equal` does (interning allowed) |
| type test | `x is a number` | `x is Number` | `TypeTest` | `x is nothing` tests `Nothing` |
| predicate | `x is empty` | `is_empty(x)` | `Call(is-empty)` | [03-grammar.md](03-grammar.md) §5.4 |
| symbolic equivalence | `a is equivalent to b using rs` | `equivalent(a, b, rs)` | `egraph-equiv` | [08-symbolic.md](08-symbolic.md) |
Bare `a is b` between two values is SAY-E0110.

## 8. Conformance
`TYP-01`…`TYP-20`, `NUM-01`…`NUM-24`, `TXT-01`…`TXT-10`, `REC-01`…`REC-12`, `COL-01`…`COL-14` in [15-conformance.md](15-conformance.md).
