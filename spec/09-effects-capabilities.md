# 09 · Effects and capabilities (seed F9, I1; F27)
Spec `0.1-lite` · edition 0. RFC 2119 keywords as in [01-principles.md](01-principles.md).

## 1. Effects
1. **Built-in effects (9):** `console`, `files`, `network`, `clock`, `random`, `environment`, `processes`, `foreign`, `tasks`. User-defined effects (`effect payments`) are v0.1.
2. A function declares its effects with `needs E [and E]` (symbols `needs E, E`), optionally narrowed: `needs network limited to "api.weather.au"`, `needs files limited to "./data", read only`.
3. **Rule 1 (static):** a function's declared effects MUST include the effects of every function it calls directly, every lambda it calls, every `with` block it opens and every concurrency construct it uses (SAY-E0501; concurrency also SAY-E0601). A v0 implementation MUST check this for calls whose callee is statically known; calls through function values are checked at run time (panic SAY-E0502).
4. A declared narrowing is a promise: the function will never use the effect outside it. The runtime enforces it by narrowing the context on entry.
5. A module header `needs` line MUST list the union of its definitions' effects (SAY-E0501); `explain` prints it as "It may use: …". A module with no header (single-file program, [10 §1](10-modules-dialects.md)) has an implied `needs` equal to that union; the formatter writes it out only when a header is present.
6. The prelude is pure except `show` and `ask` (`needs console`).

## 2. Capabilities
1. A **capability** is an unforgeable runtime value granting one effect, possibly narrowed. Edition 0 user code cannot construct, store in data structures, or inspect capabilities; it refers to them only by effect name in `needs` and `with`.
2. Capabilities are immutable. Narrowing produces a new capability that is a subset of the parent (SAY-E0504 if a narrowing would widen, e.g. narrowing `limited to "a.example"` to `limited to "b.example"`).
3. **Narrowing kinds (edition 0):**
   | Effect | `limited to` argument | `read only` |
   |---|---|---|
   | `network` | host text (`"api.weather.au"`), exact match, or `"*.example.com"` suffix match | — |
   | `files` | path text; access is limited to that directory subtree after resolving `..` and symlinks | allowed |
   | `tasks` | Integer: maximum children running at once | — |
   | `environment` | text: one variable name | — |
   | `processes` | text: one executable path | — |
   | others | not narrowable in edition 0 (SAY-E0504) | — |

## 3. The capability context (no ambient authority)
1. Every evaluation frame has an immutable **capability context**: a map from effect to capability.
2. **Root:** when `say run` starts `main`, the context contains exactly the effects in `main`'s `needs` (with their narrowings), each granted by the host only if host policy allows it. If policy refuses any, the run stops before `main` with SAY-E0506 and exit code 4. Top-level `let`s run with an empty context.
3. **Calls:** calling a function passes the caller's context restricted to the callee's declared effects, then narrowed by the callee's declared narrowings.
4. **`with E limited to X[, read only]:`** evaluates its body with `E` replaced by the narrowed capability; at block exit the narrowed capability is **revoked** (any closure that escaped with it gets panic SAY-E0502 on use).
5. **Tasks:** a child task inherits its parent's context; capabilities are immutable so sharing them is safe ([11-concurrency.md](11-concurrency.md) §7).
6. **`evaluate`** uses the caller's context and cannot extend it (SAY-E0503).
7. **Tests** start with a context containing only a capturing fake `console`, a virtual-clock `tasks`, a virtual `clock` and a seeded `random`. Real effects require `say test --allow EFFECT` and are listed in the report.
8. "hello web" budget (kill criterion 4): `to main, needs network limited to "example.com" and console:` is one capability line.

## 4. Host policy and v0 adapters
1. The host decides which effects it can grant. The v0 reference host MUST implement `console`, `files`, `clock`, `random` and `tasks`. It MUST refuse `network`, `environment`, `processes` and `foreign` with SAY-E0506 unless the implementation provides an adapter (v0.1 targets `network` and `foreign`).
2. Policy sources (highest first): command-line `--deny EFFECT` / `--allow EFFECT`, then `say.toml` `[capabilities]`, then the default "grant what `main` declares among implemented effects".
3. `--deny` always wins. The REPL starts with `console` only; `:grant` asks for confirmation.

## 5. Optional backing by atHome tokens (adapter, v0.1)
1. A host MAY back a capability with an external **capability token** checked on every use, so that authority can expire or be revoked mid-run. The reference design is the atHome token model (audience, expiry, revoke) from [ao3575911/atHome](https://github.com/ao3575911/atHome) (FACT: AGPL-3.0, last pushed 2026-05-14).
2. The adapter interface (Python, in the host):
   ```
   class CapabilityBacking(Protocol):
       def check(self, effect: str, narrowing: tuple, use: dict) -> Literal["ok", "expired", "revoked", "denied"]: ...
   ```
   Any result other than `"ok"` makes the operation return `problem capability-revoked` (with `data` carrying the reason). A revocation mid-flight in a concurrent child aggregates normally (D6).
3. **Licensing boundary:** the Sayform repository is Apache-2.0. An atHome adapter MUST live in a separate package (for example `sayform-athome`) under atHome's licence; the Sayform core MUST NOT import it. The core only defines the `CapabilityBacking` protocol.

## 6. Security model summary (F27)
| Layer | Mechanism | What it stops |
|---|---|---|
| Language | effects declared and checked; capabilities required at run time; `evaluate` cannot gain capabilities | code doing what its signature does not admit |
| Imports | `use` grants nothing; dialect expansions show their effects | a "harmless" dependency reaching the network |
| Concurrency | immutable capabilities; no capture of changeable state by tasks; narrowed capabilities revoked at scope exit | data races; capabilities leaking through tasks |
| Packages | pinned by BLAKE3 module hash over the core; no install scripts | tampered or re-tagged packages; install-time worms (N2) |
| Lockfile | every package's `needs` row recorded; growth fails `say lock --diff` (exit 5) until `--accept` | permissions quietly growing on upgrade |
| Foreign | `foreign` treated as unbounded; `strict` requires a subprocess sandbox (v1) | the escape hatch used unnoticed |
| Runtime | optional token-backed capabilities checked on every use | stolen or long-lived authority |

Out of scope until a registry exists: package signing / transparency log (UNKNOWN fit of sigstore-like systems).

## 7. Prior art
Koka row-typed effects, Unison abilities, Roc platforms, Austral linear capabilities, Deno permission flags; links in [16-prior-art.md](16-prior-art.md).

## 8. Conformance
`CAP-01`…`CAP-20` in [15-conformance.md](15-conformance.md) §10.
