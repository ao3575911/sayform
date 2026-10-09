# 07 · Semantics: evaluation, binding, functions, control flow, patterns, errors, dispatch
Covers seed F3, F5, F6, F7, F11 and F19, F20. Spec `0.1-lite` · edition 0. RFC 2119 keywords as in [01-principles.md](01-principles.md).

## 1. Evaluation model (F11)
1. Evaluation is **strict (eager), left to right, call by sharing**. A `Call` evaluates `fn`, then `args` in order, then `slots` in their canonical order, then dispatches.
2. Only `and`, `or` and `default` (`or else`) receive thunks (zero-parameter lambdas) and evaluate their right operand conditionally. `Quote` is the only way to suspend evaluation of an arbitrary expression.
3. Laziness (`stream`) is not in edition 0.
4. The v0 reference evaluator is a tree-walking interpreter over the core in which **every `eval_*` function is a Python generator** so that concurrency checkpoints can `yield` to the scheduler ([11-concurrency.md](11-concurrency.md) §8).
5. Program execution: `say run FILE` loads the module and its imports (each module's top-level `let`s are evaluated once, in source order, with no capabilities), then calls `main` if present. `main` takes no parameters and its declared `needs` determines the root capabilities ([09-effects-capabilities.md](09-effects-capabilities.md) §3).
6. Exit codes: `0` main returned normally; `1` main returned a problem (printed with the 5-part format); `2` compile errors; `4` a capability was refused by host policy (SAY-E0506); `70` panic.

## 2. Names, binding, mutability (F3)
1. `let x be E` creates an **immutable** binding. `let x be E, changeable` / `var x = E` a changeable one.
2. `set x to E` / `x := E` rebinds a changeable name; on an immutable name it is SAY-E0302.
3. `change the f of p to E` / `p.f := E` mutates a field of a value whose record type is declared `changeable` (SAY-E0303 otherwise).
4. Scope is lexical and block-level. Binding a name that is already bound **in the same block** is SAY-E0301; an inner block MAY shadow an outer binding (the formatter does not warn; OPINION, kept from Python practice).
5. There is no implicit global and no `global`/`nonlocal`. Closures capture bindings by reference; a closure that captures a changeable binding cannot be passed to a child task (SAY-E0603).
6. `=` is never assignment: an expression statement whose top node is `equal` with a bare name on the left is SAY-E0111 ("did you mean `let x be …` or `set x to …`?").

## 3. Functions (F5)
1. Declaration: `to NAME PARAMS [giving T] [, needs …] [, may fail with …] [, for any …]:` / `def NAME(…) -> T needs … fails …:`. Function names are **single words** (hyphenated where needed); spaces never occur in names.
2. Parameters: positional, `of`-lead (first only), slot (`to from by into for`), named (`with`). See [03-grammar.md](03-grammar.md) §5.2–5.3.
3. **Return is explicit:** `give back E` / `return E`. Falling off the end returns `nothing`. If the function declares `giving T` with `T` not admitting `nothing`, falling off the end is SAY-E0201 (static when every path is visible; runtime panic SAY-E0212 otherwise).
4. Defaults are evaluated at each call, in the callee's module scope, after the positional arguments.
5. Lambdas: `given x and y, E` / `(x, y) => E`; expression bodies only in edition 0. A lambda's effects are part of its function type and are checked where it is called.
6. Calls are resolved by name at check time; `fn` that is not a function value at run time panics SAY-E0212 (hint: "two names next to each other mean a call").
7. Recursion is allowed; the v0 reference interpreter MUST support a call depth of at least 1,000 and MUST report deeper recursion as panic SAY-E0212 with the message "call depth limit reached" rather than crashing the host.

## 4. Control flow (F6)
| Construct | Words | Symbols | Rule |
|---|---|---|---|
| conditional | `if c:` `otherwise if c:` `otherwise:` | `if` `elif` `else` | each `c` MUST be Truth (no truthiness) |
| loop over a collection | `for each x in xs:` | `for x in xs:` | binder is an irrefutable pattern |
| counted loop | `repeat n times:` | `for _ in 1..n:` | `n` exact Integer ≥ 0 (E0801, E0212) |
| conditional loop | `while c:` | `while c:` | |
| exit loop | `stop` | `break` | innermost loop only |
| next iteration | `skip` | `continue` | innermost loop only |
| structural match | `match v:` `when P[, if G]:` `otherwise:` | `match v:` `case P [if G]:` `else:` | first matching case wins; no fall-through |
There is no `goto`, no fall-through and no `switch`.

## 5. Pattern matching (F19)
1. Grammar: [03-grammar.ebnf](03-grammar.ebnf) §10. `?n` binds `n`; the body refers to `n`.
2. Record and case patterns are **closed** unless they end with `, and more` / `...`.
3. `or`-alternatives MUST bind the same names with the same types (SAY-E0904).
4. Exhaustiveness is checked for variants, Truth, unions with `Nothing` and finite literal sets. Non-exhaustive: SAY-W0911 (error under `strict`). A `match` that finds no case at run time panics SAY-E0212 with "no case matched".
5. `let` and `for` accept irrefutable patterns only (SAY-E0905).
6. Guards MUST be pure (SAY-E0501 if they need an effect).
7. `PQuote` patterns match Expression values structurally; pattern variables bind sub-expressions.
```say
to area of shape (a Shape) giving a number:
    match shape:
        when circle with radius ?r:
            give back 314159/100000 * r ^ 2
        when rectangle with width ?w and height ?h, if w equals h:
            give back w ^ 2
        when rectangle with width, height:
            give back width * height
```

## 6. Errors: problems, panics, cancellation (F7)
### 6.1 Problems (recoverable)
1. A **problem** is an ordinary value `problem(kind, message, data)`; `kind` is a Symbol. Create one with `problem not-found` or `problem not-found with message "no such city"`.
2. A function that can return a problem MUST declare `may fail with KIND [and KIND]` (symbols `fails KIND, KIND`). Returning an undeclared kind is SAY-E0207 when visible statically, else a panic SAY-E0212 at the return.
3. There is no `ok(...)` wrapper: a fallible function returns either its normal value or a problem.
4. `try E` / `E?`: if `E` is a problem, return it from the enclosing function immediately; otherwise yield the value. The enclosing function's `fails` MUST cover the possible kinds (SAY-E0207).
5. `E or else D` / `E ?? D` replaces `nothing` or a problem with `D`.
6. Discarding the result of a `may fail` call in an expression statement is SAY-W0201.
7. Problem kinds used by the prelude: `division-by-zero` (only `checked-divide`), `no-such-field`, `not-found`, `invalid`, `timed-out`, `several`, `capability-revoked`, `foreign-error`, `currency-mismatch`, `empty-list`, `parse-error`.

### 6.2 Panics (bugs)
1. Broken invariants and impossible states **panic**: index 0 or out of range, exact division by zero, runtime type mismatch, failed `match`, deadlock, sending on a closed channel.
2. A panic unwinds the current task with a full trace (core node path + source span per frame). Panics MUST NOT be catchable by `try`, `or else` or `match`.
3. In a concurrent block, a panicking child cancels its siblings and the parent re-panics after the join ([11-concurrency.md](11-concurrency.md) §4).
4. `say run` prints the panic in the 5-part format and exits 70.

### 6.3 Diagnostics
Every diagnostic (compile error, warning, panic, uncaught problem from `main`) uses the 5-part format and a stable code ([14-errors.md](14-errors.md)).

## 7. Capability context (summary; normative text in 09)
Effects are performed only through capabilities held in the **lexical capability context**. A call to a function that `needs E` passes the caller's capability for `E` implicitly; the caller MUST itself declare `E` (SAY-E0501) and hold it at run time (panic SAY-E0502 if a host misconfiguration leaves it absent).

## 8. Dispatch and roles (F20)
1. **Multiple dispatch:** the method is chosen by the runtime types of **all positional arguments** (FACT: the Julia manual defines multiple dispatch as "using all of a function's arguments to choose which method should be invoked").
2. A function name declared more than once in a module with different positional parameter types adds methods to one generic. Slot and named parameters MUST be identical across methods (SAY-E0407).
3. **Resolution order:** exact match → most specific (on every argument) → explicitly declared coercion (v0.1) → SAY-E0401 (static when types are known, else runtime panic E0401 is reported as SAY-E0212 with the E0401 explanation attached).
4. Two equally specific methods are SAY-E0402, **reported at definition time** with both signatures.
5. **Orphan rule:** a method may be defined only in the module that owns the generic or at least one argument type (SAY-E0403). Two active dialects defining the same method: SAY-E0404.
6. **Roles (v0.1):** named bundles of required signatures plus laws; `T plays R:` lists implementations; checked at declaration (SAY-E0405); used as generic constraints. Roles never change dispatch. Built-in roles (v0.1): `Equatable`, `Ordered`, `Hashable`, `Showable`, `Addable`, `Iterable`, `Explainable`. Default methods MAY be provided by a role and overridden only in the type's own module.
7. Edition 0 builtins dispatch internally on their argument types; user methods on builtin generics are allowed only for user-owned types (orphan rule).

## 9. Conformance
`SEM-01`…`SEM-40`, `PAT-01`…`PAT-16`, `ERRV-01`…`ERRV-12`, `DSP-01`…`DSP-10` in [15-conformance.md](15-conformance.md).
