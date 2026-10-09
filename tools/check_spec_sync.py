"""Fail if keyword lists or error codes in code drift from the spec tables.

Compares `keywords.RESERVED`/`CONTEXTUAL` with spec/02-lexical.md sections 5 and 6, and
`codes.CODES` with the registry table in spec/14-errors.md.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sayform import codes, keywords  # noqa: E402


def section(text: str, start: str, end: str) -> str:
    a = text.index(start)
    return text[a : text.index(end, a)]


def words_in_table(block: str) -> list[str]:
    out: list[str] = []
    for row in block.splitlines():
        cells = row.split("|")
        if len(cells) > 3 and "`" in cells[2]:
            out += re.findall(r"`([^`]+)`", cells[2])
    return out


def main() -> int:
    lexical = (ROOT / "spec" / "02-lexical.md").read_text(encoding="utf-8")
    reserved = words_in_table(section(lexical, "## 5. Reserved", "## 6."))
    contextual = words_in_table(section(lexical, "## 6. Contextual", "Removed from"))
    errors = (ROOT / "spec" / "14-errors.md").read_text(encoding="utf-8")
    spec_codes = {"SAY-" + m for m in re.findall(r"^\| ([EWPH]\d{4}) \|", errors, re.M)}
    checks = [
        ("reserved words", set(reserved), set(keywords.RESERVED)),
        ("contextual words", set(contextual), set(keywords.CONTEXTUAL)),
        ("error codes", spec_codes, set(codes.CODES)),
    ]
    bad = 0
    for name, spec, code in checks:
        if spec == code:
            print(f"ok   {name}: {len(spec)} in sync")
            continue
        bad += 1
        print(
            f"FAIL {name}: missing in code {sorted(spec - code)}; not in spec {sorted(code - spec)}"
        )
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
