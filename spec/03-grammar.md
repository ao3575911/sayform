# 03 · Grammar: both surfaces, precedence and ambiguity rules
Spec `0.1-lite` · edition 0. The formal grammar is [03-grammar.ebnf](03-grammar.ebnf); this file is normative prose that the EBNF relies on. RFC 2119 keywords as in [01-principles.md](01-principles.md).

## 1. One grammar, two surfaces
1. An implementation MUST accept the words surface, the symbols surface and any mix of the two in one file. Each alternative in the EBNF is tagged (W) or (S); untagged productions are shared.
2. The **module header**, `with … limited to …:`, `together:`, `within …:`, `simplify … using …`, `ruleset` blocks and `check "label":` blocks print identically in both surfaces.
3. `say fmt` reprints a file in exactly one surface (F-R2, [13-tooling.md](13-tooling.md) §2).
4. The parser produces a concrete tree that is immediately **lowered** to the core ([04-core-ast.md](04-core-ast.md) §3). Error messages refer to source spans kept in the side table.

## 2. Word classes used by the grammar
| Class | Definition |
|---|---|
| `WORD` | identifier ([02-lexical.md](02-lexical.md) §4.1) that is not a reserved word and is not a contextual word in the current slot |
| `TYPENAME` | `WORD` with an uppercase initial |
| `TYPEWORD` | in type slots only: `number` `integer` `decimal` `rational` `approx` `truth` `symbol` `expression` `problem` `type` `capability` |
| `PLURALWORD` | in type slots only: the plural of a built-in type word (`numbers` `integers` `decimals` `rationals` `approxes` `truths` `symbols` `expressions` `problems` `types` `lists` `sets` `maps` `functions` `channels`) or the declared/derived plural of a user type ([05-types-values.md](05-types-values.md) §2.3). `text`, `money`, `anything` are mass nouns and have no plural |
| `UNITWORD` | a unit name declared by the active `units` dialect |
| `DURATION` | time quantity literal ([02-lexical.md](02-lexical.md) §4.5) |
| `MONEYLIT` / `QUANTITYLIT` | literals that exist only under dialect `money` / `units` |

Type words are not reserved: `number` is an ordinary name outside type slots. The compound-type heads `list` `set` `map` `channel` `function` `quantity` and the mass nouns `text` `money` `anything` are type words in the same sense (03-grammar.ebnf §9); they are neither reserved nor contextual keywords and do not count toward either budget.

## 3. Precedence ladder (high binds tighter)
| Level | Name | Words forms | Symbols forms | Assoc |
|---|---|---|---|---|
| P15 | primary | literals, names, `(…)`, `quote (…)`, `the symbol x`, `[…]`, `{…}`, `from a to b`, `item i of c`, `problem k`, `given x, …`, `each x in c, …`, `the type …` | `` `(…) ``, `'x`, `x => …`, `List[T]` | — |
| P14 | application / possession | `x's f`, `the f of x` (right), prefix call `f x`, `f of x`, slots, `with` named args | `x.f`, `x?.f`, `x[i]`, `x?[i]`, `f(…)`, postfix `x?` | left (`'s`, `.`), right (`of`) |
| P13 | *(reserved)* | unit literals are lexical under dialect `units` | | — |
| P12 | power | `a to the power of b` | `a ^ b` | **right** |
| P11 | unary | `negative a`, `try a` | `-a` | prefix |
| P10 | multiplicative | `times`, `divided by`, `divided by …, rounded down`, `mod` | `*` `/` `//` `%` | left |
| P9 | additive | `plus`, `minus` | `+` `-` | left |
| P8 | range | (`from a to b` is P15) | `a..b`, `a..<b`, `… by s` | none |
| P7 | postfix clauses | `where`, `each`, `sorted [by k][, descending]`, `grouped by`, `joined with`, `joined by`, `in UNIT` | `++` | left, chained |
| P6 | comparison | `equals`, `is …` phrases, `contains`, `matches`, `is equivalent to … using …` | `=` `==` `!=` `<` `<=` `>` `>=` `===` `in` `~=` | **non-associative**; only the between chain |
| P5 | not | `not` | `!` | prefix |
| P4 | and | `and` | `&&` | left |
| P3 | or | `or` | `\|\|` | left |
| P2 | absence | `or else` | `??` | **right** |
| P1 | pipeline | `then` | `\|>` | left |
| P0 | statements | `let … be`, `set … to`, `add … to`, `change … to`, `rewrite … as` | `let … =`, `var`, `:=`, `+=`, `=>` (in rulesets) | — |

16 levels (P0–P15). P13 is reserved and unused by the core.

## 4. Disambiguation rules (normative, applied in this order)
| Rule | Statement |
|---|---|
| **R1 type slots** | Type phrases are parsed **only** in type slots: after `giving`, inside `(…)` of a parameter or field, after `is a/an`, after `let x:`, after `the type`, after `?x (` in patterns, and in symbols after `:` / `->` / `[`. In value position `a`/`an` followed by a type word is SAY-E0107; any other article outside a slot is SAY-E0104. |
| **R2 postfix clauses** | A postfix clause attaches to the longest preceding P8+ expression and clauses chain left to right. The body of `where` / `each` (`cond`) cannot contain a postfix clause unless parenthesised, so `xs where it > 0 sorted by size` = `sort_by(filter(xs, …), …)`. |
| **R3 possession** | `of` binds right and `'s` binds left, both at P14: `the name of the owner of car` = `car.owner.name`; `car's owner's name` = the same. |
| **R4 comma** | A comma ends the current clause; a modifier after a comma (`descending`, `exclusive`, `rounded down`, `changeable`, `read only`, `if any`) belongs to the nearest preceding clause that accepts it. A modifier no clause accepts is SAY-E0130. |
| **R5 ambiguity** | If two readings remain after R1–R20 and resolution does not settle them, the implementation MUST report SAY-E0108 showing both readings and the symbols form for each. It MUST NOT pick one. |
| **R6 prefix call** | In a words prefix call `f x` / `f of x`, the argument is `pc_arg` (P11 and above, plus postfix clauses). If the token after the argument is a P8–P10 operator (`+ - * / // % .. ..<`, `plus minus times divided mod`), that is SAY-E0108 with readings `(f x) op y` and `f (x op y)`. Comparisons, `and`, `or`, `or else`, `then`, commas, slot words and line ends end the call without error: `if count of xs is at least 3:` is `(count of xs) >= 3`. |
| **R7 slots** | Immediately after a callee or after a call argument, a slot word (`to from by into for`) always starts a slot. To pass a words range as a positional argument, parenthesise it: `show (from 1 to 10)`. |
| **R8 block openers** | `all of` / `first of` open a concurrent block only when `of` is followed by `:` and a line end; otherwise `first of xs` is a call to `first`. (D4, locked.) |
| **R9 `in`** | `x in Y` is unit conversion iff dialect `units` is active and `Y` is a `UNITWORD`; if `Y` is also a bound value name, SAY-E0108. Otherwise it is membership. |
| **R10 implicit `it`** | Inside a `where`/`each`/`sorted by`/`grouped by` body, a bare name that is not bound locally means a field of `it`. If a local of that name exists **and** the element type is a record with that field (or unknown), SAY-E0108. |
| **R11 `with` after a callee** | `X with name v [and name v]`: if `X` resolves to a record type → construction; to a function definition or builtin → named arguments; to a local value → copy-with (`RecordLit` with `base`). |
| **R12 `and` in named args** | After a named argument, `and` continues the list only if followed by a `WORD` and a token that can start an operand; otherwise it is logical `and`. |
| **R13 `or else`** | `or` immediately followed by `else` is the absence operator (P2), never logical `or`. |
| **R14 chains** | Comparisons are non-associative. The only allowed chain is `lo OP x OP hi` with both `OP` from {`<`, `<=`} or both from {`>`, `>=`}; it lowers to `between`. Every other chain (`a = b = c`, `a < b > c`, any words-form chain) is SAY-E0121. |
| **R15 and/or mixing** | Mixing `and` and `or` without brackets is warning SAY-W0116; the formatter inserts the brackets that match the parse (`and` binds tighter). |
| **R16 `add` statement** | `add` at the start of a statement is the add-to statement iff the logical line has the exact shape `add pc_arg to WORD`; otherwise `add` is an ordinary name. |
| **R17 `=>`** | At line level inside a `ruleset` block, `=>` separates a rule's sides; everywhere else `=>` is a lambda arrow. |
| **R18 apostrophe** | Lexical, [02-lexical.md](02-lexical.md) §4.2. |
| **R19 hyphen** | Lexical, [02-lexical.md](02-lexical.md) §4.1: `a-b` is one name, `a - b` and `x-1` are subtraction. The formatter always prints binary minus with spaces. |
| **R20 type application** | In expression position `TYPENAME [ … ]` is a type value (`TypeExpr`), never indexing (values cannot have uppercase names, SAY-E0126). |

### 4.1 Worked examples
1. `let ranked be a list of numbers sorted by size` → `let … be` is value position, so `a list of numbers` is not a type phrase (R1) → **SAY-E0107**: "`a list of numbers` names a type, but a value is expected here." Try: `let ranked: a list of numbers be numbers sorted by size`.
2. `show count of people where age is at least 18` → `show (count of (people where it's age >= 18))`. R6: the argument of `count of` absorbs the `where` clause; R2/R10: `age` is a field of `it`. The formatter prints `show count of (people where age is at least 18)` (F-R8).
3. `give back sum of xs / count of xs` → **SAY-E0108** (R6), readings `(sum of xs) / (count of xs)` and `sum of (xs / count of xs)`. Try the first, parenthesised.
4. `if 1 < x < 10:` → `between(x, 1, 10, low-inclusive=no, high-inclusive=no)`; words print `if x is between 1 and 10, exclusive:`.
5. `send m to bob with retries 3 and timeout 5 seconds` → `send(m, to=bob, retries=3, timeout=5s)` (R7, R12).
6. `let p2 be p with age 37` (p local) → copy-with (R11). `Person with name "Ada" and age 36` → construction.

## 5. Statement-level notes
### 5.1 Top level
A module's top level MAY contain declarations, notes, checks and **immutable** `let` bindings whose value is pure. Any other statement at top level is SAY-E0130 with the hint "put it inside `to main`". Executable code lives in functions; `say run` calls `main`.

### 5.2 Function headers
1. Words: `to NAME PARAMS [giving TYPE] {, CLAUSE}:`. Clause order is printed as: `needs`, `may fail with`, `for any`, `explained as` (F-R11). The parser accepts any order.
2. A parameter's `lead` is part of the signature. `of` MAY appear only on the first parameter and makes it positional with the `of` lead (`to average of numbers …` is called `average of xs`). `to from by into for` mark slot parameters (called with the slot word). `with` marks a named parameter (called `with NAME value`). A parameter with no lead is positional.
3. Positional parameters MUST precede slot and named parameters. Duplicate leads or names are SAY-E0407.
4. A function with two or more positional parameters prints in the words surface in paren-call form `f(a, b)`; words prefix calls support at most one positional argument.

### 5.3 Calls
1. Positional arguments bind to positional parameters in order; slot arguments by slot word; named arguments by name. Unknown slot or name: SAY-E0408. Missing argument without default: SAY-E0409. Extra or duplicate arguments: SAY-E0410.
2. In symbols, slot arguments are written as keyword arguments with the slot word (`to=bob`) and named arguments with their name (`retries=3`).
3. A zero-argument call is written `f()` in both surfaces.

### 5.4 `is` + adjective
`x is WORD` (and `x is not WORD`) where `WORD` is not a comparison phrase resolves to the function `is-WORD` applied to `x` (`x is empty` → `is-empty(x)`). If `is-WORD` is not defined: if `WORD` is a bound value, SAY-E0110 ("bare `a is b` between two values; did you mean `a equals b`?"), otherwise SAY-E0115 with suggestions. Adjectives are an open set; no adjective is a keyword.

### 5.5 Text interpolation
`{expr}` inside text parses `expr` with the full expression grammar. The value is converted with `display` ([12-stdlib.md](12-stdlib.md) §2). Interpolation is the only implicit conversion to text.

### 5.6 Patterns in each position
| Position | `WORD` means | Refutable allowed? |
|---|---|---|
| `let`, `for`, lambda parameters | a binder | no (SAY-E0905) |
| `match` case | a variant case with no fields; a binder is written `?WORD` | yes |
| `rewrite` left side / `matches` right side | a literal name inside the quoted expression; `?WORD` binds | yes |

## 6. Conformance
`GRM-01`…`GRM-30` in [15-conformance.md](15-conformance.md) §3 test every rule R1–R20 with a positive and a negative program.
