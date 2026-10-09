# 08 · Symbolic core: symbols, quote, evaluate, rulesets, rewrite, simplify, equivalence (seed F4, I4)
Spec `0.1-lite` · edition 0. RFC 2119 keywords as in [01-principles.md](01-principles.md).

## 1. Symbols
1. `'x` / `the symbol x` is an interned `Symbol` that compares by name (canonical `-` spelling, so `'read_csv` equals `'read-csv`).
2. Symbols are values; they are never evaluated.
3. Problem kinds, sort modes and other enumerations in the prelude are Symbols.

## 2. Expressions are data (homoiconic core)
1. An `Expression` value is an expression-family core node (tags 28–44 except `Unquote` outside a quote) together with its sub-nodes. It is immutable and compares structurally (spans ignored).
2. Names inside a quoted expression are **unresolved** (`Name` with `ref = Builtin(sym)` for builtins, otherwise `Local`-free symbolic names); resolution happens only when the expression is evaluated.
3. Inspection (prelude): `head of e` returns a Symbol — the builtin function name for an operator call (`'add`), the callee name for other calls, or the node kind (`'get`, `'index`, `'lit`, `'name`, …) — and `arguments of e` returns a List of Expressions/values. These two functions plus quote/unquote are sufficient to build and take apart any expression.

## 3. Quote and unquote
1. `quote (E)` / `` `(E) `` returns the core of `E` without evaluating it. Parentheses are REQUIRED in both surfaces.
2. `~e` inside a quote evaluates `e` at quote time and splices the result: an Expression is inserted as is; a plain value (number, text, truth, nothing, symbol) is inserted as a `Lit`/`SymLit`; any other value is panic SAY-E0212.
3. `~` outside a quote is SAY-E0901. Nested quotes are allowed; `~` belongs to the innermost quote.
```say
let n be 3
let e be quote (x * (~n + 0))      # x * (3 + 0)
```

## 4. `evaluate`
1. `evaluate e [with bindings m]` evaluates Expression `e` in a fresh scope whose only names are the prelude plus the entries of `m` (a Map from Symbol to value).
2. It runs **under the caller's capability context only**. An effectful call inside `e` whose effect is not in the caller's context panics SAY-E0503. `evaluate` therefore requires no `needs` of its own, but code that evaluates expressions which perform effects MUST declare those effects to hold them (OPINION: simplest sound rule).
3. Unbound symbols return `problem not-found` (so `evaluate` is declared `may fail with not-found`).
4. `evaluate` MUST NOT define new top-level names, rulesets, dialects or capabilities.

## 5. Rulesets and rewrite rules
1. `ruleset NAME:` declares a module-scoped ruleset; its body contains only rules.
2. Rule forms: `rewrite L as R [when G]` (words) / `L => R [if G]` (symbols). `L` is an expression pattern in which `?a` are pattern variables; `R` is a template that MAY use the pattern variables of `L` (SAY-E0902 otherwise); `G` is a pure Truth guard over them.
3. Rules are **never global** (Law 3): a ruleset can be imported by name like any definition, but applying it is always explicit (`simplify … using r`). Attempting to declare a rule outside a ruleset, or to mark a ruleset as applying automatically, is SAY-E0903.
4. Pattern variables match any sub-expression; a variable occurring twice in `L` requires structurally equal sub-expressions.
```say
ruleset algebra:
    rewrite ?a + 0 as ?a
    rewrite ?a * 1 as ?a
    rewrite ?a * 0 as 0
    rewrite ?a * (?b + ?c) as ?a * ?b + ?a * ?c
```

## 6. `simplify`
1. `simplify e using rs [with nodes N and steps K]` returns an Expression equal to `e` under the rules of `rs` with **minimal cost**.
2. **Cost** (edition 0): the number of core nodes in the term. Ties are broken by the lexicographically smallest SCS-1 serialisation ([04-core-ast.md](04-core-ast.md) §5). This makes results deterministic across backends.
3. **Budget:** defaults `nodes 10000` (e-nodes or rewrite-tree nodes) and `steps 30` (saturation iterations or rewrite passes). When the budget is reached the best term found so far is returned and warning SAY-W0912 is emitted to the diagnostics stream (not to `console`).
4. **Backends:**
   - **Pure fallback (REQUIRED in v0):** bottom-up rewriting to a fixpoint, applying every rule at every node each pass, keeping the cheapest term seen. It is not complete for non-confluent rulesets; that is acceptable for v0.
   - **E-graph backend (OPTIONAL extra, v0.1):** equality saturation via the `egglog` Python package (FACT: PyPI `egglog` 14.0.0, Python ≥ 3.12, MIT; repo `egraphs-good/egglog-python`). The backend MUST return a term at least as cheap as the pure fallback's on the same input and budget, or fall back to it.
5. Conformance tests for `simplify` only assert results where the minimal-cost term is unique within the budget.
6. Rationale: equality saturation does not depend on rule order (FACT: egglog combines equality saturation and Datalog), which avoids Wolfram-style rule-order surprises; scoping avoids action at a distance.

## 7. Equivalence
1. `a is equivalent to b using rs` / `equivalent(a, b, rs)` / `a ≡ b using rs` returns `yes` if `a` and `b` are proven equal under `rs` within the budget, `no` if both saturated to distinct normal forms without exceeding the budget, and `nothing` (unknown) otherwise, with SAY-W0912.
2. The pure fallback proves equivalence by simplifying both sides and comparing; it returns `no` only when both sides reached a fixpoint within budget.

## 8. `matches`
`e matches P` / `e ~= P` returns a Map from pattern-variable Symbol to Expression when `e` matches the quoted pattern `P`, else `nothing`.
```say
match (quote (2 * (y + 1))) matches quote (?a * (?b + ?c)):
    when nothing:
        show "no match"
    when ?bindings:
        show bindings
```

## 9. Conformance
`SYM-01`…`SYM-24` in [15-conformance.md](15-conformance.md) §9.
