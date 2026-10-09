# Contributing

## Spec first
`spec/` is the source of truth. Code follows the spec, never the other way round.
If the spec is silent, ambiguous or wrong, open an issue titled
`spec: <file> §<n> — <problem>` with the `spec-gap` label, implement the most
conservative reading, mark the code with `# spec-gap #<issue>`, and continue.
Changes to `spec/` go in their own PR whose title starts `spec:` and which adds a
`spec/CHANGELOG.md` entry; the maintainer merges those.

## Small PRs
One milestone slice per PR. Every PR needs green CI (`test` check) and is squash-merged.

## Tests
- Unit tests live in `tests/`; name tests after their conformance id (`test_lex_04_tab`).
- A conformance test is `conformance/<area>/<TEST-ID>.say` plus `<TEST-ID>.expect.toml`
  in the format of spec/15-conformance.md §1. The runner discovers them automatically.
- Golden files change only with a spec change.

## Budgets
`python tools/check_budgets.py` must pass: 63 reserved words, 89 contextual words,
44 core nodes, 74 builtins, 96 error codes, 2 runtime dependencies, at most 8,000
interpreter lines. If a change needs more, open an issue instead.

## Commit style
`area: summary`, for example `lexer: reject tabs in indentation`.
