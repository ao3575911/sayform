# 12 · Standard library: the v0 surface (F23)
Spec `0.1-lite` · edition 0. RFC 2119 keywords as in [01-principles.md](01-principles.md).

## 1. Budget and rules
1. **v0 builtin budget: 74 functions** = **53 host primitives** (implemented in the host language) + **21 prelude functions written in Sayform** (`prelude/*.say` in the repository). Plus 1 prelude record type (`Pair`) and 1 prelude constant (`empty-set`).
2. **The prelude is pure except `show` and `ask`.** Every effectful function lives in a module whose functions declare `needs` (`files`, `clock`, `random`, `tasks`).
3. Every builtin MUST have: the signature below, an `explain` noun-phrase template, at least one conformance test (`LIB-<name>`), and documented panics/problems.
4. Functions are listed in words-header form; the symbols form follows mechanically (`to length of t (text) giving an integer` ⇄ `def length(of t: Text) -> Integer`). Naming convention: noun-like functions take the `of` lead (`length of t`, `sum of xs`); verb-like functions take their first argument directly (`show x`, `send 5 into ch`, `take 3 from xs`).
5. Implementations MUST NOT add further names to the prelude in edition 0. Extra modules (`use …`) MAY exist but are not part of conformance.

## 2. Host primitives (53)
### 2.1 Core (8)
| # | Signature | Notes / errors |
|---|---|---|
| 1 | `to equal a b giving a truth` | structural; operator `=` |
| 2 | `to same a b giving a truth` | identity; operator `===` |
| 3 | `to not of a (a truth) giving a truth` | E0212 non-Truth |
| 4 | `to and a (a truth) b (a function from nothing to truth) giving a truth` | thunk; short-circuit |
| 5 | `to or a (a truth) b (a function from nothing to truth) giving a truth` | thunk; short-circuit |
| 6 | `to default a b (a function from nothing to anything) giving anything` | `or else`; triggers on `nothing` and problems only |
| 7 | `to problem kind (a symbol) with message (text, default "") with data (a map from symbols to anything, default {}) giving a problem` | |
| 8 | `to display of value giving text` | canonical text form used by interpolation and `show`: numbers as written/normalised (`approx` prefix for Approx), text unquoted at top level and quoted inside collections, records `Person with name "Ada" and age 36` in words; Expressions in the canonical ASCII symbols surface (`x * y`); problems as `problem KIND: MESSAGE` |

### 2.2 Console (2) — `needs console`
| # | Signature | Notes / errors |
|---|---|---|
| 9 | `to show value, needs console` | writes `display of value` and a line end |
| 10 | `to ask prompt (text) giving text, needs console, may fail with not-found` | reads one line; end of input → `not-found` |

### 2.3 Numbers (10)
| # | Signature | Notes / errors |
|---|---|---|
| 11 | `to add a b giving a number` | `+`; E0202, E0203, E0204, E0212 |
| 12 | `to subtract a b giving a number` | `-` |
| 13 | `to multiply a b giving a number` | `*` |
| 14 | `to divide a b giving a number` | `/`; panic E0841 |
| 15 | `to floor-divide a b giving an integer` | `//`; panic E0841 |
| 16 | `to modulo a b giving a number` | `%`; panic E0841 |
| 17 | `to power a b giving a number` | `^`; panic E0842 |
| 18 | `to negate of a giving a number` | unary `-` |
| 19 | `to less a b giving a truth` | `<`; E0212 unordered |
| 20 | `to round x (a number) with places (an integer, default 0) with mode (a symbol, default 'half-even) giving a number` | modes `'half-even`, `'half-up` |

### 2.4 Text (9)
| # | Signature | Notes / errors |
|---|---|---|
| 21 | `to length of t (text) giving an integer` | grapheme clusters (Unicode 15.1.0) |
| 22 | `to uppercase of t (text) giving text` | Unicode default case mapping (`str.upper`) |
| 23 | `to lowercase of t (text) giving text` | `str.lower` |
| 24 | `to join a b giving anything` | `++`; Text×Text or List×List; E0202 |
| 25 | `to split t (text) by separator (text) giving a list of text` | empty separator → E0212 |
| 26 | `to trim t (text) giving text` | removes leading/trailing White_Space characters |
| 27 | `to code-points of t (text) giving a list of integers` | |
| 28 | `to utf8-bytes of t (text) giving a list of integers` | |
| 29 | `to parse-number t (text) giving a number, may fail with parse-error` | accepts the INTEGER/DECIMAL lexical forms, optional leading `-` |

### 2.5 Collections (7)
| # | Signature | Notes / errors |
|---|---|---|
| 30 | `to range a b with exclusive (a truth, default no) with step (a number, default 1) giving a list of numbers` | lazy-friendly but materialised in v0; E0802, E0801 |
| 31 | `to added c item giving anything` | list append, set insert, map merge |
| 32 | `to count of c giving an integer` | List, Set, Map, Text (graphemes) |
| 33 | `to sort-by of c key (a function from anything to anything) with descending (a truth, default no) giving a list of anything` | stable; panic E0803 mixed key types |
| 34 | `to contains c x giving a truth` | List, Set, Map keys, Text substring, range |
| 35 | `to keys of m (a map from anything to anything) giving a list of anything` | insertion order |
| 36 | `to values of m (a map from anything to anything) giving a list of anything` | insertion order |

### 2.6 Symbolic (6)
| # | Signature | Notes / errors |
|---|---|---|
| 37 | `to evaluate of e (an expression) with bindings (a map from symbols to anything, default {}) giving anything, may fail with not-found` | caller's capabilities only; panic E0503 |
| 38 | `to match e (an expression) pattern (an expression) giving a map from symbols to expressions or nothing` | `matches` |
| 39 | `to egraph-simplify e (an expression) rules (a ruleset) with nodes (an integer, default 10000) with steps (an integer, default 30) giving an expression` | `simplify … using …`; W0912 |
| 40 | `to egraph-equiv a (an expression) b (an expression) rules (a ruleset) giving a truth or nothing` | `is equivalent to`; W0912 |
| 41 | `to head of e (an expression) giving a symbol` | [08-symbolic.md](08-symbolic.md) §2 |
| 42 | `to arguments of e (an expression) giving a list of anything` | |

### 2.7 Tasks (7) — `needs tasks`
| # | Signature | Notes / errors |
|---|---|---|
| 43 | `to new-channel with capacity (an integer, default 0) giving a channel of anything, needs tasks` | |
| 44 | `to send value into ch (a channel of anything), needs tasks` | panics E0610; E0602 |
| 45 | `to receive from ch (a channel of anything) giving anything or nothing, needs tasks` | |
| 46 | `to close ch (a channel of anything), needs tasks` | panic E0611 |
| 47 | `to sleep for d (a quantity of time), needs tasks` | checkpoint |
| 48 | `to map-concurrent of c f (a function from anything to anything) giving a list of anything, needs tasks` | `at the same time` |
| 49 | `to received of ch (a channel of anything) giving a list of anything, needs tasks` | iterable for `for each … received from` (yields lazily in the evaluator) |

### 2.8 Host-effect modules (4)
| # | Signature | Notes / errors |
|---|---|---|
| 50 | `files.read-text path (text) giving text, needs files, may fail with not-found` | UTF-8; path checked against the `files` narrowing |
| 51 | `files.write-text content (text) to path (text), needs files` | refused under `read only` (panic E0502) |
| 52 | `clock.now giving a decimal, needs clock` (called `clock.now()`) | seconds since the Unix epoch as an exact Decimal with scale 6; virtual in tests |
| 53 | `random.random-integer from low (an integer) to high (an integer) giving an integer, needs random` | inclusive; seeded in tests |

## 3. Prelude written in Sayform (21)
These MUST be implemented in `.say` source in `prelude/` and are part of conformance, so the language is exercised by its own library.
| # | Signature | Definition sketch |
|---|---|---|
| 54 | `to less-eq a b giving a truth` | `not (less b a)` |
| 55 | `to greater a b giving a truth` | `less b a` |
| 56 | `to greater-eq a b giving a truth` | `not (less a b)` |
| 57 | `to between x lo hi with low-inclusive (a truth, default yes) with high-inclusive (a truth, default yes) giving a truth` | composed from `less` / `less-eq` |
| 58 | `to absolute of x (a number) giving a number` | `if x is less than 0: give back negative x` |
| 59 | `to checked-divide a (a number) by b (a number) giving a number, may fail with division-by-zero` | `if b equals 0: give back problem division-by-zero` |
| 60 | `to join-all of items (a list of text) by sep (text) giving text` | loop with `++` |
| 61 | `to map of c f (a function from anything to anything) giving anything` | loop with `added` |
| 62 | `to filter of c f (a function from anything to truth) giving anything` | loop with `added` |
| 63 | `to sort of c giving a list of anything` | `sort-by(c, given x, x)` |
| 64 | `to first of c giving anything or nothing` | `item 1 of c, if any` |
| 65 | `to last of c giving anything or nothing` | `item -1 of c, if any` |
| 66 | `to take n (an integer) from c giving a list of anything` | `n > count` → whole list |
| 67 | `to drop n (an integer) from c giving a list of anything` | |
| 68 | `to sum of c giving a number` | empty → `0` |
| 69 | `to group-by of c key (a function from anything to anything) giving a map from anything to lists of anything` | first-seen key order |
| 70 | `to zip a (a list of A) b (a list of B) giving a list of Pair, for any A and B` | stops at the shorter list |
| 71 | `to is-empty of c giving a truth` | `count of c equals 0` |
| 72 | `to reversed of c (a list of anything) giving a list of anything` | |
| 73 | `to largest of items (a list of T) giving a T or nothing, for any T` | `last of (items sorted)` |
| 74 | `to smallest of items (a list of T) giving a T or nothing, for any T` | `first of (items sorted)` |

Prelude types and constants: `a Pair of A and B has a left (A) and a right (B)`; `empty-set`.

**Note on `take`/`drop` calls:** `take 3 from xs` (positional `n`, slot `from`). The seed's `first 3 of c` form is replaced by `take 3 from c` (CHANGELOG C-14).

## 4. Dialect libraries (not in the v0 budget)
| Dialect | Functions |
|---|---|
| `money` | `convert of m to currency (a symbol) with rate (a decimal)`, `checked-add a b` (may fail with `currency-mismatch`) |
| `units` | `convert of q to unit` (also `q in UNIT`), `dimension of q` |
| `ieee` | `is-nan of x`, `is-infinite of x` |

## 5. Not in edition 0
`compare`/`Order` (with roles, v0.1), locale collation, regular expressions, JSON, HTTP, dates beyond `clock.now`, `stream`, property-test generators (v0.1 `testing` module), Python bridge (v0.1).
