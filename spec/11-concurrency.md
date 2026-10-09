# 11 · Structured concurrency (F16)
Spec `0.1-lite` · edition 0. RFC 2119 keywords as in [01-principles.md](01-principles.md). Decisions D4 and D6 are locked.

## 1. Stance
Structured concurrency only: child tasks cannot outlive the block that starts them; tasks communicate through channels; no shared mutable state; concurrency is the effect `tasks`. v0 runs on a deterministic single-threaded scheduler; real threads are v1. Prior art (Trio nurseries, Kotlin coroutines, Java StructuredTaskScope, Swift task groups, Go channels, Python TaskGroup/PEP 654) is in [16-prior-art.md](16-prior-art.md).

## 2. Constructs
| Construct | Kind | Children | Result | When a child fails |
|---|---|---|---|---|
| `together:` | statement | each direct statement is one task | — | cancel siblings, wait for them, then the block fails with the aggregated problem (§4) |
| `all of:` / `all_of:` | block expression (whole value of `let`/`set`/`give back`/statement) | each line `[label:] expr` is one task | unlabelled → List in source order; all labelled → anonymous record; mixing labelled and unlabelled lines is SAY-E0130 | same as `together` |
| `first of:` / `first_of:` | block expression | each line `expr` is one task | value of the **first child to succeed**; the rest are cancelled (D4) | failures are ignored while other children run; if **every** child fails → aggregated problem |
| `each x in c at the same time, E` | expression | one task per element, bounded by the `tasks` narrowing | List in input order | same as `all of` |
| `within D:` | statement | its own body (a cancel scope, not a task) | — | when `D` elapses the body is cancelled and `problem timed-out` is raised at the `within` as if by `try` (the enclosing function MUST declare `timed-out`, SAY-E0207) |

1. `first of` opens a block only when `of` is followed by `:` and a line end (R8); otherwise it is the collection function.
2. A `together` child MUST NOT be a bare `let` (SAY-E0604): bindings inside a child are invisible to siblings and to the parent.
3. All constructs require the `tasks` effect (SAY-E0601). `D` in `within` MUST be a time quantity (SAY-E0605).
```say
to dashboard for city (text) giving a Dashboard, needs network and tasks, may fail with not-found and several and timed-out:
    within 3 seconds:
        let parts be all of:
            weather: fetch-forecast for city
            rates: fetch-rates for "AUD"
        give back Dashboard with weather parts's weather and rates parts's rates
```

## 3. Cancellation
1. **Cooperative.** Cancellation sets a flag on a task subtree and takes effect at the task's next **checkpoint**: `send`, `receive`, `sleep`, entering or leaving any construct in §2, any call to a function that `needs tasks`, and (in v0) every loop back-edge.
2. A cancelled task unwinds: `with` blocks revoke their narrowed capabilities; channel ends it held stay open (closing is explicit).
3. Cancellation is **not** a problem value: `try`, `or else` and `match` cannot observe it.
4. Direction: parent → all descendants. A child cannot cancel its parent; it can only fail.
5. No shielding in edition 0 (OPEN O-1).
6. **Guarantee:** when a `together`, `all of` or `first of` block exits, every child has finished. No task leaks.

## 4. Error aggregation (D6, locked)
1. The first child failure triggers cancellation of the siblings. Problems from siblings that fail before reaching a checkpoint are also collected; children that were only cancelled add nothing.
2. **Exactly one problem** passes through **unwrapped**.
3. **Two or more** become `problem several` with `data` = `{'problems: [p1, p2, …]}` in children's source order. The checker adds `several` to the required `fails` set of any function containing a construct with two or more children that can fail; missing it is SAY-E0606 ("add `several` to `may fail with`").
4. **Panics:** a panicking child cancels its siblings and the parent **re-panics** after the join, with the child's trace plus "while running child (b) of `together` at L12".
5. When every child of `first of:` fails: the single problem if there was one child, else `several`.

## 5. Channels (module `tasks`, prelude functions)
| Operation | Words | Symbols | Semantics |
|---|---|---|---|
| create | `let ch: a channel of numbers be new-channel with capacity 10` | `let ch: Channel[Number] = new_channel(capacity=10)` | capacity 0 (default) = unbuffered rendezvous |
| send | `send 5 into ch` | `send(5, into=ch)` | blocks until there is room or a receiver; sending on a closed channel **panics** (SAY-E0610); only immutable values may be sent (SAY-E0602) |
| receive | `receive from ch` | `receive(from=ch)` | `T or nothing`; `nothing` once the channel is closed **and drained**, never a zero value |
| close | `close ch` | `close(ch)` | closing twice panics (SAY-E0611) |
| iterate | `for each x received from ch:` | `for x in received(ch):` | ends when closed and drained |
| ends | `ch's sender` / `ch's receiver` | `ch.sender` / `ch.receiver` | one-direction handles (attenuation) |
| select | — | — | v1 (not in edition 0) |
`send`, `receive`, `close`, `new-channel`, `received` are functions, not keywords. A user function `send message to bob` is distinct because its slot set differs (`to` vs `into`).

## 6. Time
1. `within` and `sleep` use the **monotonic clock that comes with the `tasks` capability**; reading wall-clock time needs `clock`.
2. Nested `within`: the earliest deadline wins.
3. `sleep for 2 seconds` / `sleep(for=2s)` is a checkpoint.

## 7. Capabilities and state across tasks
1. Capabilities are immutable and unforgeable, so a child MAY use any capability in its lexical context; that is explicit, never ambient. A child MAY narrow further with `with`.
2. A child task MUST NOT capture a changeable binding or a changeable record (SAY-E0603). Take an immutable snapshot first: `let snapshot be cart`.
3. A capability narrowed inside a child is revoked when that child ends. A token-backed capability is checked on every use; revocation mid-flight gives that child `problem capability-revoked`, which aggregates normally.
4. `tasks limited to N` bounds concurrently running children (`map-concurrent` waits for a slot).

## 8. The v0 single-threaded scheduler
1. The evaluator is written as Python generators from day one; checkpoints `yield` to the scheduler. No greenlet or asyncio dependency.
2. State: a FIFO ready deque; a min-heap of timers keyed by `(deadline, sequence number)`; per-channel send and receive wait queues (FIFO); the task tree (parent, children in source order, cancel flag, collected problems).
3. Order: children start in source order and run round-robin between checkpoints. The same program always produces the same interleaving.
4. **Deadlock:** if no task is ready, no timer is pending and at least one task is blocked, the scheduler panics SAY-E0612 listing the blocked tasks and what each waits on.
5. `say test` runs on a **virtual clock** (a `within 5 seconds` test finishes instantly). `--shuffle-tasks SEED` perturbs the ready-queue order deterministically from `SEED`.
6. Limit: a blocking host call (file read) blocks every task in v0; `explain` notes it on functions that need `files`. v1 moves blocking calls to worker threads.

## 9. Conformance
`CON-01`…`CON-22` in [15-conformance.md](15-conformance.md) §12.
