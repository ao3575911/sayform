# 10 · Modules, dialects, editions and the lockfile (seed F8, F10; F26, F27)
Spec `0.1-lite` · edition 0. RFC 2119 keywords as in [01-principles.md](01-principles.md).

## 1. Modules (F8)
1. One file is one module. The header, in this fixed order (SAY-E0702 otherwise; F-R10):
   ```say
   module shop.cart
   edition 0
   use shop.prices: price-of, discount
   use text-tools as tt
   needs files
   dialect money
   ```
2. `module NAME` MAY be omitted only in a single-file program; the name is then the file stem. When present, `shop.cart` MUST live at `shop/cart.say` relative to the package root (SAY-E0701).
3. `edition N` MAY be omitted (W1012; edition 0 assumed); under `strict` it is REQUIRED (SAY-E1012).
4. `use M` makes `M`'s exports reachable as `last-segment.name` (or `alias.name`); `use M: a, b` imports names directly. There is no star import (the seed's `strict`-only ban becomes universal; SAY-E0305 is kept for `use M: *`).
5. **`use` grants no capabilities** (Law 2).
6. Edition 0 exports every top-level definition and constant. Module-private definitions are not in edition 0 (OPEN item O-3).
7. Cyclic imports are SAY-E0701 with the cycle printed (OPINION: keeps loading order trivial).
8. Module search: the package root (directory containing `say.toml`, or the file's directory) and, for packages, `say.lock` entries resolved into `.say/packages/<hash>/`.

## 2. Dialects (F10, I7)
1. A **dialect** is a module that exports grammar sugar, operators, unit/currency tables and rulesets. A module enables dialects in its header: `dialect units, money`.
2. **Scope:** lexical per module; never global; no reopening of built-in types, keywords or operators (Law 3).
3. **Hygiene:** expansions get fresh names (Racket-style hygiene). Expansions MUST lower to core nodes (SAY-E0704 otherwise). A dialect MUST NOT add evaluation semantics.
4. **Effects:** if sugar expands to effectful code, those effects appear in the user's effect row.
5. **Conflicts:** two active dialects claiming the same word, symbol or method: SAY-E0705 / SAY-E0404 at the header. Unknown dialect: SAY-E0706.
6. **Printing:** dialect sugar prints in dialect form only when the dialect is in the module header (F-R7); otherwise as the call it lowers to.
7. **Edition 0 built-in dialects:**
   | Dialect | Adds | Profile |
   |---|---|---|
   | `strict` | requires `edition`, annotations on exports (E0205), ASCII identifiers (E0124), exhaustive matches (W0911→error), no unbounded `foreign` (E0712), no `quick-script` (E0505) | v0 |
   | `money` | money literals, currency table, `checked-add`, `convert … to … with rate` | v0.1 |
   | `units` | unit literals, dimensions, `in UNIT` conversion | v0.1 |
   | `ieee` | IEEE 754 inf/NaN semantics for `Approx` | v0.1 |
   | `quick-script` | ambient root capabilities for one-file scripts, with a warning printed on every run | v0.1 |
   A v0 implementation MUST implement `strict` and MUST reject the others with SAY-E1013.
8. **User dialects (v0.1):** declared with `dialect NAME:` containing `operator` declarations (see [06-operators.md](06-operators.md) §5), functions and rulesets. Operator words MUST NOT clash with reserved words or active contextual words.
9. **Localised keyword sets (v1):** lexer-only dialects that map 1:1 onto the 63 reserved words, so they lower to the same core and hash (Hedy-style).

## 3. Editions (F26)
1. Every module has an edition. **Edition 0** is unstable until `SAY-SPEC-1`; then edition 1 freezes.
2. An edition fixes: the reserved and contextual word lists, the lowering table, the formatter's canonical choices (including the article exception table), the node catalogue, the default dialects and the pinned Unicode version.
3. Editions interoperate **through the core**: modules from different editions link because they share core nodes. A node introduced in a newer edition MUST NOT appear in an older-edition module (SAY-E1011).
4. New keywords and canonical-phrasing changes only arrive at edition boundaries; within an edition only bug fixes, and `say fmt` output stays stable.
5. `say migrate --to-edition N` is mechanical, may rename user names that collide with new keywords, and shows a diff.
6. The core version `sayform/core/1` is in the hash header; changing it re-hashes everything and is announced in advance.
7. Dialects follow [Semantic Versioning](https://semver.org/) and declare `stable since EDITION`; within a major version a dialect cannot change how its sugar lowers (`say lock` checks the dialect's expansion hash).
8. Proposed cadence: at most one edition per year (OPINION).

## 4. Packages
1. A package is a directory with `say.toml` (name, version, edition, `surface = "words" | "symbols"`, `[capabilities]` policy, `[dependencies]`).
2. Packages are pinned by **module hash** (BLAKE3 over the core, [04-core-ast.md](04-core-ast.md) §6). Names are for humans; hashes are for machines.
3. Packages have **no install scripts**; nothing runs at install time.
4. A registry is out of scope for v0 and v0.1; dependencies are fetched from git URLs or local paths and verified by hash (SAY-E0703 on mismatch).

## 5. Lockfile `say.lock` (format is normative)
```
say-lock 1
package weather-au 1.4.0
    source git+https://example.org/weather-au@v1.4.0
    hash   b3:<52 base32 characters>
    needs  network limited to "api.weather.au"
    dialects expansion b3:<52 base32 characters>
```
1. One `package` stanza per dependency, sorted by name; fields in the order shown; two-space values aligned as printed by `say lock`.
2. `needs` records the package's exported effect row **with narrowings**.
3. `say lock --diff` compares against the committed lockfile and **exits 5** when any package's `needs` grew (new effect, wider narrowing, or `foreign`), printing:
   ```
   -   needs  network limited to "api.weather.au"
   +   needs  network limited to "api.weather.au" and files limited to "~/.cache" and foreign
       ! needs grew: files, foreign (unbounded). Run `say lock --accept weather-au` to allow.
   ```
4. `say lock --accept PKG` records the new row. CI SHOULD run `say lock --diff`.
5. The lockfile MAY record a test hash per package to reuse cached test results (v0.1).

## 6. Conformance
`MOD-01`…`MOD-14`, `DIA-01`…`DIA-08`, `LOCK-01`…`LOCK-06` in [15-conformance.md](15-conformance.md) §11.
