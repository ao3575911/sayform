# 02 · Lexical grammar (F1, F23)
Spec `0.1-lite` · edition 0. RFC 2119 keywords as defined in [01-principles.md](01-principles.md).

## 1. Source text
1. Source files MUST be UTF-8 ([RFC 3629](https://www.rfc-editor.org/rfc/rfc3629)). Invalid UTF-8 is SAY-E0105.
2. A leading U+FEFF BYTE ORDER MARK MAY appear at offset 0 and is ignored. Anywhere else it is SAY-E0105.
3. Line ends are U+000A LINE FEED, or U+000D U+000A (CR LF), which is read as one LF. A lone U+000D is SAY-E0105.
4. File extension `.say`; test files `*.test.say`.
5. Identifiers MUST be in Unicode Normalization Form C ([UAX #15](https://www.unicode.org/reports/tr15/)). A non-NFC identifier is SAY-E0105 (the formatter MAY offer the NFC spelling). Text literal contents are not normalised.
6. Edition 0 pins **Unicode 15.1.0** for every Unicode property the lexer or the `text` module uses (FACT: CPython 3.13.5 `unicodedata.unidata_version` is `15.1.0` on the build box; Python 3.12 ships 15.0.0, which is acceptable for NFC because of the Unicode normalization stability policy).

## 2. Layout
1. **Indentation** is significant. One level is exactly 4 U+0020 SPACE characters.
2. U+0009 CHARACTER TABULATION in indentation is SAY-E0101. Indentation that is not a multiple of 4 is SAY-E0102.
3. A block opens with a trailing `:` (U+003A) at the end of a logical line; the next non-blank line MUST be indented one level deeper (else SAY-E0131).
4. A **logical line** ends at a line end that is not inside `(` `)`, `[` `]` or `{` `}`. Inside brackets, line ends and indentation are insignificant. There is **no** other implicit continuation and no backslash continuation.
5. Blank lines and comment-only lines do not affect indentation.
6. A `.` (U+002E) as the last non-comment character of a logical line is optional sentence punctuation; it is discarded by the lexer and removed by the formatter.
7. The lexer emits `NEWLINE`, `INDENT` and `DEDENT` tokens with the Python algorithm ([Python lexical analysis §2.1.8](https://docs.python.org/3/reference/lexical_analysis.html)); Lark's `Indenter` is a suitable implementation ([Lark indented-tree example](https://lark-parser.readthedocs.io/en/stable/examples/indented_tree.html)).

## 3. Character inventory (every character with a meaning)
ASCII suffices for every program. The non-ASCII characters in §3.2 are **optional aliases**; the formatter prints ASCII unless `say fmt --unicode` is given.

### 3.1 ASCII (REQUIRED)
| Char | Code point | Name | Uses |
|---|---|---|---|
| (space) | U+0020 | SPACE | separator, indentation |
| `!` | U+0021 | EXCLAMATION MARK | `!` not, `!=` not equal |
| `"` | U+0022 | QUOTATION MARK | text literals `"…"`, `"""…"""` |
| `#` | U+0023 | NUMBER SIGN | comment to end of line |
| `$` | U+0024 | DOLLAR SIGN | money prefixes `A$`, `US$`, `NZ$` (dialect `money` only) |
| `%` | U+0025 | PERCENT SIGN | modulo |
| `&` | U+0026 | AMPERSAND | `&&` and |
| `'` | U+0027 | APOSTROPHE | possessive `'s`; symbol literal `'x` |
| `(` `)` | U+0028 U+0029 | PARENTHESES | grouping, calls, parameters, type phrases in words |
| `*` | U+002A | ASTERISK | multiply |
| `+` | U+002B | PLUS SIGN | `+` add, `++` join, `+=` add-to |
| `,` | U+002C | COMMA | separators; clause end |
| `-` | U+002D | HYPHEN-MINUS | subtract, negate, identifier joiner, `->` result type |
| `.` | U+002E | FULL STOP | field access, decimal point, `..` `..<` ranges, `...` rest pattern, optional sentence end |
| `/` | U+002F | SOLIDUS | `/` divide, `//` floor divide |
| `0`–`9` | U+0030–U+0039 | DIGITS | number literals |
| `:` | U+003A | COLON | block opener, type annotation, map entry, `:=` rebind |
| `<` | U+003C | LESS-THAN SIGN | `<`, `<=`, `..<` |
| `=` | U+003D | EQUALS SIGN | `=` / `==` equality, `===` identity, `=>` lambda/rule, `:=`, `+=`, `!=`, `<=`, `>=`, `~=`, keyword arguments `name=` |
| `>` | U+003E | GREATER-THAN SIGN | `>`, `>=`, `->`, `\|>`, `=>` |
| `?` | U+003F | QUESTION MARK | `?NAME` pattern variable, postfix `?` try, `??` default, `?.` and `?[` optional access, `T?` optional type |
| `A`–`Z` `a`–`z` | U+0041–U+005A, U+0061–U+007A | LATIN LETTERS | words |
| `[` `]` | U+005B U+005D | SQUARE BRACKETS | list literals, indexing, generic types |
| `\` | U+005C | REVERSE SOLIDUS | escapes inside text only |
| `^` | U+005E | CIRCUMFLEX ACCENT | power |
| `_` | U+005F | LOW LINE | identifier joiner (same name as `-`), wildcard pattern `_` |
| `` ` `` | U+0060 | GRAVE ACCENT | quote `` `(…) `` |
| `{` `}` | U+007B U+007D | CURLY BRACKETS | map and set literals; interpolation inside text |
| `\|` | U+007C | VERTICAL LINE | `\|\|` or, `\|>` pipeline, type union, variant case separator |
| `~` | U+007E | TILDE | `~e` unquote, `~=` matches |

ASCII characters not listed (`;` U+003B, `@` U+0040) have no meaning in edition 0; outside text and comments they are SAY-E0105.

### 3.2 Optional non-ASCII aliases
| Char | Code point | Name | ASCII equivalent | Notes |
|---|---|---|---|---|
| `≠` | U+2260 | NOT EQUAL TO | `!=` | |
| `≤` | U+2264 | LESS-THAN OR EQUAL TO | `<=` | |
| `≥` | U+2265 | GREATER-THAN OR EQUAL TO | `>=` | |
| `∈` | U+2208 | ELEMENT OF | `in` | membership only |
| `≡` | U+2261 | IDENTICAL TO | `equivalent(a, b, using=rs)` | infix `a ≡ b using rs` |
| `€` | U+20AC | EURO SIGN | `EUR` | dialect `money` only |
| `£` | U+00A3 | POUND SIGN | `GBP` | dialect `money` only |

The seed's `Σ` (U+03A3) and `#c` count forms are **removed** (`#` starts a comment; see CHANGELOG C-07). A dialect MAY declare further operator aliases, which MUST be real assigned Unicode scalar values outside the Private Use Areas and MUST each have an ASCII or words twin ([10-modules-dialects.md](10-modules-dialects.md) §3).

## 4. Tokens
### 4.1 Words (identifiers)
```
WORD      = START { CONT | JOINER START }
START     = XID_Start                                  (UAX #31)
CONT      = XID_Continue                               (UAX #31; includes digits and "_" itself is NOT used here)
JOINER    = "-" | "_"                                  (U+002D or U+005F, immediately between two characters)
```
1. A joiner MUST be immediately preceded by a `CONT`/`START` character and immediately followed by an XID_Start character (a letter). So `total-cost`, `read_csv` and `base64-encode` are single words; `x-1` is `x` `-` `1`; `level_2` is SAY-E0105 ("a joiner must be followed by a letter; write `level2`").
2. **`-` and `_` are the same name (D3, locked).** The canonical form stores `-`. The words printer prints `-`; the symbols printer prints `_`. Declaring two names that differ only by joiner spelling in one scope is SAY-E0113.
3. A word MUST NOT start with a joiner. The lone character `_` is the wildcard token, not a word.
4. Implementation note: a candidate is a valid word iff `w.replace("-", "_").isidentifier()` holds in Python 3.12+, it contains no `__`, it does not start or end with a joiner, and every joiner is followed by a letter ([UAX #31](https://www.unicode.org/reports/tr31/)).
5. **Case rules.** Type, record, variant and role names MUST start with an uppercase letter (General Category Lu or Lt). Binding, function, field, slot, case, effect and module-segment names MUST NOT start with an uppercase letter. Violations are SAY-E0126. Type variables are a single uppercase-initial word (`T`, `Item`).
6. **Keyword case.** A word of length ≥ 2 that equals a reserved word under Unicode case folding but is not all lowercase is SAY-E0103 (`Let`, `IF`). Single letters are exempt so type variables `A`, `B` work.
7. Under `dialect strict`, words MUST be ASCII (SAY-E0124; mitigates confusables, see [UTS #39](https://www.unicode.org/reports/tr39/)).

### 4.2 Symbol literal and possessive
1. `'` immediately following a word character, `)` or `]`, and immediately followed by `s` and then a character that is not XID_Continue, is the **possessive token `'s`**.
2. `'` preceded by whitespace, an opening bracket, `,` or start of line, and immediately followed by a `START` character, begins a **symbol literal** `'WORD`.
3. Any other `'` is SAY-E0105. Plural possessive (`people'`) is not supported; write `the f of people`.

### 4.3 Numbers
```
INTEGER   = "0" | NONZERO { DIGIT }
DECIMAL   = INTEGER "." DIGIT { DIGIT }
APPROXLIT = "approx" WS ( DECIMAL | INTEGER ) [ ("e"|"E") ["-"|"+"] DIGIT {DIGIT} ]
```
1. Literals are non-negative; `-5` is `negate(5)`.
2. Leading zeros (`007`), digit separators (`1_000`), `.5`, `5.` and exponent notation outside `approx` are SAY-E0135.
3. `0.1` is an **exact decimal** with scale 1. Scale is kept as written (`12.50` has scale 2).
4. A number immediately followed by letters is SAY-E0135 unless the letters are a time-unit suffix (§4.5) or a unit/currency suffix declared by an active dialect.
5. `approx` (contextual) followed by a number gives a binary64 literal. The seed's `0.1f` suffix is removed (CHANGELOG C-08).

### 4.4 Text
1. `"…"` single-line text; `"""…"""` multi-line text (the first line end after the opening `"""` is dropped; common leading indentation equal to the closing `"""` line's indentation is removed).
2. Escapes: `\\` `\"` `\{` `\}` `\n` `\t` and `\u{H…}` with 1–6 hex digits naming a Unicode scalar value (not a surrogate). Any other escape is SAY-E0136.
3. `{ expr }` inside text is interpolation. A literal brace is written `\{` or `\}`.
4. A line end inside `"…"` or end of file inside any text literal is SAY-E0106.

### 4.5 Durations (core, no dialect needed)
A number followed by one of these contextual unit words (with a space) or suffixes (no space) is a **time quantity literal**: `millisecond` `milliseconds` (`ms`), `second` `seconds` (`s`), `minute` `minutes` (`min`). Example: `within 5 seconds:` / `within 5s:`. All other units require `dialect units`.

### 4.6 Comments and notes
1. `#` (outside text) starts a comment that runs to the end of the line. Comment text is kept verbatim as trivia.
2. `note:` at the start of a logical line starts a documentation note; indented following lines continue it. Attachment rules: [04-core-ast.md](04-core-ast.md) §8.

### 4.7 Operator tokens (longest match wins)
```
=== == => = != <= >= < > := += ++ + -> - ** (not a token: SAY-E0105) * // / % ^
?? ?. ?[ ? ~= ~ |> || | && ! ..< ... .. . , : ( ) [ ] { } ` 's '
```
`**` is listed only to state that it is not an operator (use `^`); the lexer reports SAY-E0105 with that hint.

## 5. Reserved words: exactly 63 (D5, locked)
None of these can ever be used as a name (SAY-E0109).

| Group | Words | # |
|---|---|---|
| Binding | `let` `be` `set` `to` `change` `var` | 6 |
| Functions and errors | `give` `return` `giving` `given` `needs` `may` `with` `try` | 8 |
| Control | `if` `otherwise` `else` `match` `when` `for` `each` `in` `repeat` `while` `stop` `skip` | 12 |
| Logic and comparison | `and` `or` `not` `is` `equals` `contains` | 6 |
| Articles and possession | `the` `a` `an` `of` `'s` | 5 |
| Clauses | `by` `where` `then` `from` | 4 |
| Symbolic | `quote` `evaluate` `rewrite` `as` `simplify` `using` `ruleset` | 7 |
| Modules | `module` `use` `dialect` `effect` | 4 |
| Concurrency | `together` `within` | 2 |
| Data | `has` `role` | 2 |
| Literals | `yes` `no` `nothing` `true` `false` | 5 |
| Docs and tests | `note` `check` | 2 |
| **Total** | | **63** |

`true`/`false` are accepted and always reprinted as `yes`/`no`. `contains` is accepted and reprinted as `is in` (F-R3). `role` is reserved in edition 0 although roles are a v0.1 feature.

## 6. Contextual words: exactly 89 (closed, edition 0)
Each word is a keyword **only** in the slot shown; anywhere else it is an ordinary name. Binding one as a name is warning SAY-W0114. A dialect MAY add contextual words (for example unit names) that are active only in modules that enable it; those do not count toward this list.

| # | Word(s) | Slot where it is a keyword |
|---|---|---|
| 1 | `back` | after `give` |
| 2 | `fail` | after `may` |
| 3 | `times` | after `repeat EXPR`; and in binary-operator position (multiply) |
| 4 | `up` | `up to` (exclusive range end) |
| 5–13 | `less` `greater` `than` `at` `least` `most` `equal` `same` `between` | comparison phrases after `is` / `is not` |
| 14 | `equivalent` | `is equivalent to … using …` |
| 15 | `one` | `is one of:` (variant definition) |
| 16–18 | `exclusive` `above` `below` | after a comma ending `is between …`; `above`/`below` also in `binds above/below` (dialects) |
| 19 | `descending` | after a comma ending `sorted by …` |
| 20–21 | `rounded` `down` | `, rounded down` after `divided by …` |
| 22 | `changeable` | after a comma in `let …` or a record definition |
| 23 | `default` | after a comma inside a parameter or field type phrase |
| 24 | `plural` | `(plural WORD)` after a record or variant name |
| 25 | `limited` | `EFFECT limited to EXPR` in `needs` and `with` |
| 26–27 | `read` `only` | `, read only` after a `files` narrowing |
| 28 | `edition` | module header line |
| 29–34 | `plus` `minus` `divided` `mod` `negative` `power` | operator positions (binary after an operand; `negative` prefix; `power` in `to the power of`) |
| 35–37 | `joined` `sorted` `grouped` | postfix clause after an operand |
| 38 | `matches` | binary-operator position |
| 39 | `item` | operand start: `item I of C` |
| 40 | `problem` | operand start followed by a word: `problem KIND` |
| 41 | `approx` | before a number literal |
| 42–43 | `all` `first` | block openers `all of:` / `first of:` (only when `of` is followed by `:` and a line end) |
| 44–45 | `all-of` `first-of` | symbols block openers `all_of:` / `first_of:` |
| 46 | `time` | `at the same time` |
| 47 | `received` | `for each x received from CH:` |
| 48 | `any` | `for any T` (generics); `, if any` (optional access) |
| 49 | `that` | `check that`; `for any T that plays R` |
| 50 | `fails` | `check that … fails with`; symbols function header `fails K` |
| 51–52 | `example` `gives` | inside a `note:` example line |
| 53 | `it` | implicit element inside postfix clauses |
| 54–55 | `anything` `more` | patterns (`anything` wildcard; `, and more` open record); `anything` also a type word |
| 56–57 | `symbol` `type` | after `the`: `the symbol x`, `the type …` |
| 58–64 | `def` `elif` `break` `continue` `record` `variant` `case` | symbols-surface statement openers at the start of a logical line |
| 65 | `into` | call slot word |
| 66–74 | `millisecond` `milliseconds` `second` `seconds` `minute` `minutes` `ms` `s` `min` | after a number literal (§4.5) |
| 75–81 | `operator` `operands` `binds` `like` `left` `right` `means` | inside a `dialect` block (v0.1) |
| 82–83 | `plays` `Self` | role implementation and role signatures (v0.1) |
| 84–87 | `python` `c` `wasm` `library` | after `use` (foreign; v0.1/v1) |
| 88 | `explained` | `, explained as "TEMPLATE"` in a function header (v0.1) |
| 89 | `add` | at the start of a statement of the exact shape `add EXPR to NAME` (rebind with `added`) |

Removed from the source docs' contextual list (CHANGELOG C-03): `uses`, `holding`, `its`, `whichever`, `comes`, `empty` (adjectives are open, see [03-grammar.md](03-grammar.md) §5.4), `rounded to` as a phrase.

Type words (`number`, `list`, `text`, … — full list in [03-grammar.md](03-grammar.md) §1) are a third class: recognised only inside type slots, never keywords, outside both budgets.

**Metanotation.** Spec prose and tables use `→` (U+2192), `×` (U+00D7), `…` (U+2026), `·` (U+00B7), `—` (U+2014), `⊆` (U+2286) and `⊇` (U+2287) to describe rules. They are not Sayform tokens; in source they are SAY-E0105 (except inside text literals and comments).

## 7. Literal words
`yes` `no` (Truth), `nothing` (Nothing), `true`/`false` (input aliases). `empty-set` is a prelude constant, not a keyword.

## 8. Lexical conformance
Tests `LEX-01`…`LEX-24` in [15-conformance.md](15-conformance.md) §2 cover every rule above, and every code in group 01 has an `ERR-` test.
