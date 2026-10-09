# 06 · Operators (seed §4)
Spec `0.1-lite` · edition 0. RFC 2119 keywords as in [01-principles.md](01-principles.md). Precedence levels: [03-grammar.md](03-grammar.md) §3. Lowering: [04-core-ast.md](04-core-ast.md) §3.

## 1. Rules common to all operators
1. Every operator lowers to a call of a builtin open generic (column "Function"). Printers recognise the callee and print the operator form; a hand-written call prints as the operator.
2. Canonical forms: words column first spelling; symbols column first spelling (F-R3, F-R4). Other spellings are accepted input and reprinted canonically.
3. Every operator MUST have: a static error path where the condition is detectable at check time, a runtime error path (panic code or problem kind), and a conformance test (column "Test", defined in [15-conformance.md](15-conformance.md) §6).
4. No operator performs truthiness, Text↔Number coercion, or implicit approx→exact conversion.
5. Mixed exact/approx arithmetic yields approx ([05-types-values.md](05-types-values.md) §3).

## 2. Expression operators
| ID | Words (canonical first) | Symbols | Arity | Prec | Assoc | Function | Types | Edge cases | Errors | Test |
|---|---|---|---|---|---|---|---|---|---|---|
| OP-01 | `a plus b` | `a + b` | 2 | P9 | L | `add` | Num×Num→Num; Qty×Qty same dim; Money×Money same ccy | no overflow; exact+approx→approx | E0202 Text+Num; E0203; E0204; E0212 runtime | OPT-01 |
| OP-02 | `a minus b` | `a - b` | 2 | P9 | L | `subtract` | as `add` | money may go negative | as OP-01 | OPT-02 |
| OP-03 | `negative a` | `-a` | 1 | P11 | prefix | `negate` | Num, Qty, Money | `-0` exact is `0`; `approx -0.0` kept | E0212 | OPT-03 |
| OP-04 | `a times b` | `a * b` | 2 | P10 | L | `multiply` | Num×Num; Num×Qty→Qty; Qty×Qty (dim product); Money×Num→Money | List×Int is an error (no list repetition operator in edition 0) | E0201 Money×Money, List×Int; E0212 | OPT-04 |
| OP-05 | `a divided by b` | `a / b` | 2 | P10 | L | `divide` | exact/exact→normalised exact; Qty/Qty | `1 / 4` → `0.25`; `1 / 3` → `1/3` | **panic E0841** exact zero; approx zero panics unless `ieee` | OPT-05 |
| OP-06 | `a divided by b, rounded down` | `a // b` | 2 | P10 | L | `floor-divide` | Num→Integer | toward −∞ | panic E0841 | OPT-06 |
| OP-07 | `a mod b` | `a % b` | 2 | P10 | L | `modulo` | Num | sign follows divisor | panic E0841 | OPT-07 |
| OP-08 | `a to the power of b` | `a ^ b` | 2 | P12 | **R** | `power` | exact^Integer→exact; ^non-Integer→Approx | `0 ^ 0` = 1; `2 ^ 3 ^ 2` = 512 | panic E0842 negative base with non-Integer exponent; E0841 for `0 ^ -1` | OPT-08 |
| OP-09 | `a equals b` | `a = b`, `a == b` | 2 | P6 | none | `equal` | any×any structural | `1 = 1.0` yes; exact vs approx by exact value | E0111 if `=` used as a statement (`x = 5`); E0121 chain | OPT-09 |
| OP-10 | `a is not equal to b` | `a != b`, `≠` | 2 | P6 | none | `not(equal)` | any×any | | E0121 chain | OPT-10 |
| OP-11 | `a is less than b` | `a < b` | 2 | P6 | none | `less` | ordered types (Num, Text, Qty same dim, Money same ccy) | Text compares by code point | E0201 Text<Num; E0204; E0212 | OPT-11 |
| OP-12 | `a is at most b` | `a <= b`, `≤` | 2 | P6 | none | `less-eq` | as `less` | | as OP-11 | OPT-12 |
| OP-13 | `a is greater than b` | `a > b` | 2 | P6 | none | `greater` | as `less` | | as OP-11 | OPT-13 |
| OP-14 | `a is at least b` | `a >= b`, `≥` | 2 | P6 | none | `greater-eq` | as `less` | | as OP-11 | OPT-14 |
| OP-15 | `x is between lo and hi` [`, exclusive`] [`, exclusive above`] [`, exclusive below`] | `lo <= x <= hi`, `lo < x < hi`, `lo <= x < hi`, `lo < x <= hi` (and descending mirrors) | 3 | P6 | — | `between` | ordered | each operand evaluated once, in core order `x`, `lo`, `hi` whatever the surface; `lo > hi` gives `no` | E0121 any other chain | OPT-15 |
| OP-16 | `not a` | `!a` | 1 | P5 | prefix | `not` | Truth only | no truthiness | E0112 static; E0212 runtime | OPT-16 |
| OP-17 | `a and b` | `a && b` | 2 | P4 | L | `and(a, thunk b)` | Truth | short-circuits | E0112; E0212; W0116 when mixed with `or` | OPT-17 |
| OP-18 | `a or b` | `a \|\| b` | 2 | P3 | L | `or(a, thunk b)` | Truth | short-circuits; **not** a default | E0112 with hint `or else`; E0212 | OPT-18 |
| OP-19 | `x is in c` (`c contains x` accepted) | `x in c`, `∈` | 2 | P6 | none | `contains(c, x)` | c: List, Set, Map (keys), Text (substring), range | | E0201; E0212; E0108 with units `in` | OPT-19 |
| OP-20 | `x is not in c` | `!(x in c)` | 2 | P6 | none | `not(contains)` | as OP-19 | | as OP-19 | OPT-20 |
| OP-21 | `a is the same as b` | `a === b` | 2 | P6 | none | `same` | any | interning allowed for immutables | — (total) | OPT-21 |
| OP-22 | `x is a number`, `x is nothing`, `x is not a …` | `x is Number` | 2 | P6 | — | `TypeTest` node | type on right | | E0107 if a value is on the right; E0304 unknown type | OPT-22 |
| OP-23 | `x is ADJ`, `x is not ADJ` | `is_ADJ(x)` | 1 | P6 | — | `is-ADJ` | per predicate | adjectives are open | E0115; E0110 | OPT-23 |
| OP-24 | `a joined with b` | `a ++ b` | 2 | P7 | L | `join` | Text×Text; List×List | | E0202 Text++Num (hint `"{n}"`); E0212 | OPT-24 |
| OP-25 | `items joined by sep` | `join_all(items, sep)` | 2 | P7 | — | `join-all` | List of Text × Text | empty list → `""` | E0201; E0212 | OPT-25 |
| OP-26 | `c each E` · `each x in c, E` | `map(c, x => E)` | 2 | P7 | L | `map` | List T → List U; Set; Map values | `it` is the element | E0212 non-iterable | OPT-26 |
| OP-27 | `c where cond` | `filter(c, it => cond)` | 2 | P7 | L | `filter` | collection → same kind | cond MUST be Truth | E0212 | OPT-27 |
| OP-28 | `c sorted by k[, descending]` | `sort_by(c, it => k[, descending=yes])` | 2 | P7 | L | `sort-by` | key ordered | stable | E0803 mixed key types (runtime panic E0803) | OPT-28 |
| OP-29 | `c sorted` | `sort(c)` | 1 | P7 | — | `sort` | ordered elements | stable | E0803 | OPT-29 |
| OP-30 | `c grouped by k` | `group_by(c, it => k)` | 2 | P7 | L | `group-by` | → Map from key to List | keys in first-seen order | E0212 | OPT-30 |
| OP-31 | `from a to b [by s]` · `from a up to b` | `a..b [by s]` · `a..<b` | 2–3 | P15 (W) / P8 (S) | none | `range` | Integer, Decimal, Rational, time Qty | empty when `a > b` and `s > 0` | E0802 step 0; E0801 approx bounds | OPT-31 |
| OP-32 | `a or else b` | `a ?? b` | 2 | P2 | **R** | `default(a, thunk b)` | `T or nothing`/problem × T → T | only `nothing` and problem values trigger it; `0`, `""`, `no` do not | — (total) | OPT-32 |
| OP-33 | `p's f, if any` | `p?.f` | 2 | P14 | L | `Get(optional=yes)` | | `nothing` target → `nothing` | E0206 when typed | OPT-33 |
| OP-34 | `item i of c, if any` | `c?[i]` | 2 | P14 | L | `Index(optional=yes)` | | out of range → `nothing` | E0181 literal 0 | OPT-34 |
| OP-35 | `p's f` · `the f of p` | `p.f` | 2 | P14 | L (`'s`, `.`) / R (`of`) | `Get` | record field, capability field, channel end | | E0206; problem `no-such-field` (untyped) | OPT-35 |
| OP-36 | `item i of c` | `c[i]` | 2 | P14 | L | `Index` | List (1-based), Map (key) | `c[-1]` last; `c[a..b]` slice | E0181; panics E0831, E0832 | OPT-36 |
| OP-37 | `f x`, `f of x`, slots, `with n v` | `f(x, slot=v, n=v)` | n | P14 | — | `Call` | per signature | | E0108 (R6); E0408–E0410; E0401 | OPT-37 |
| OP-38 | `a then f [slots]` | `a \|> f` | 2 | P1 | L | `Call(f, [a], …)` | | lowest precedence | as OP-37 | OPT-38 |
| OP-39 | `try e` | `e?` | 1 | P11 / P14 | prefix / postfix | `Try` | | a problem returns from the function | E0207 | OPT-39 |
| OP-40 | `quote (e)` | `` `(e) `` | 1 | P15 | — | `Quote` | → Expression | no evaluation; names stay unresolved | body must parse (its own grammar errors, e.g. E0108); E0901 if `~` appears outside any quote | OPT-40 |
| OP-41 | `~e` | `~e` | 1 | P15 | prefix | `Unquote` | e: Expression or literal value | splices | E0901 outside quote; E0212 non-expression value | OPT-41 |
| OP-42 | `the symbol x` | `'x` | 0 | P15 | — | `SymLit` | → Symbol | | E0105 malformed | OPT-42 |
| OP-43 | `e matches P` | `e ~= P` | 2 | P6 | none | `match(e, quote P)` | → Map from Symbol to Expression, or `nothing` | | E0904 | OPT-43 |
| OP-44 | `a is equivalent to b using rs` | `equivalent(a, b, rs)`, `a ≡ b using rs` | 3 | P6 | none | `egraph-equiv` | → `yes`, `no`, or `nothing` (unknown) | `nothing` when the budget was hit (W0912) | E0304 unknown ruleset | OPT-44 |
| OP-45 | `simplify e using rs` | same | 2 | P15 | — | `egraph-simplify` | Expression → Expression | returns best-so-far on budget (W0912) | E0304; E0212 | OPT-45 |
| OP-46 | `evaluate e [with bindings m]` | `evaluate(e[, bindings=m])` | 1–2 | P15 | — | `evaluate` | Expression → Anything | caller's capabilities only | panic E0503 if an effect is not in the context; problem `not-found` for unbound symbols | OPT-46 |
| OP-47 | `x in UNIT` (dialect `units`) | same | 2 | P7 | L | `convert` | Qty → Qty | exact rational factors | E0203; E0108 | OPT-47 |
| OP-48 | `each x in c at the same time, E` | `map_concurrent(c, x => E)` | 2 | P15 | — | `map-concurrent` | List → List (input order) | bounded by `tasks` narrowing | E0601; E0603; aggregation per D6 | OPT-48 |

## 3. Statement operators (P0)
| ID | Words | Symbols | Core | Errors | Test |
|---|---|---|---|---|---|
| ST-01 | `let x be E` | `let x = E` | `Bind(mutable=no)` | E0301; E0905; E0111 for `x = E` | OPT-S1 |
| ST-02 | `let x be E, changeable` | `var x = E` | `Bind(mutable=yes)` | E0301 | OPT-S2 |
| ST-03 | `set x to E` | `x := E` | `Rebind` | E0302 | OPT-S3 |
| ST-04 | `add E to x` | `x += E` | `Rebind(x, added(x, E))` | E0302; E0212 | OPT-S4 |
| ST-05 | `change the f of p to E` | `p.f := E` | `SetField` | E0303; E0206 | OPT-S5 |
| ST-06 | `rewrite L as R [when G]` | `L => R [if G]` | `Rule` | E0902; E0903 | OPT-S6 |

## 4. `or`, `or else`, `and`: what they never do
1. `or`/`and`/`not` accept Truth only; Python's `x or default` is SAY-E0112 suggesting `or else`.
2. `or else` tests absence only: `0 or else 5` is `0`.

## 5. Overload and extension protocol (seed §4.3)
1. Each operator's function is an **open generic with multiple dispatch** over the runtime types of its positional arguments ([07-semantics.md](07-semantics.md) §8).
2. **Orphan rule:** a method may be defined only in the module that owns the generic or at least one argument type (SAY-E0403).
3. **Laws** (`associative`, `commutative`, `identity 0`) are declared on roles (v0.1) and drive `say test --laws` (v0.1).
4. Resolution: exact match → most specific → coercion explicitly declared by the type owner (v0.1) → SAY-E0401. No implicit Text↔Number coercion, ever.
5. New operators are declared only in dialects (v0.1): word form, optional symbol (a real Unicode scalar with an ASCII/words twin), arity, precedence **relative** to an existing level (SAY-E0406), associativity, and the function it means. Conflicts between active dialects: SAY-E0404 / E0705.
```say
dialect vectors:
    operator "dot" (symbol "·") with 2 operands, binds like times, left to right, means dot-product
    to dot-product a (a Vector) b (a Vector) giving a number:
        give back sum of (zip(a's items, b's items) each it's left * it's right)
```
(`·` is U+00B7 MIDDLE DOT; its ASCII twin is the word `dot`.)
