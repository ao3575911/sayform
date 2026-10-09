"""Generate src/sayform/codes.py from spec/14-errors.md (the error registry).

Run: python tools/gen_codes.py   (check mode: --check exits 1 on drift)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "spec" / "14-errors.md"
OUT = ROOT / "src" / "sayform" / "codes.py"
ROW = re.compile(r"^\| ([EW]\d{4}) \| ([^|]*) \|(.*)\|\s*$")


def split_cells(rest: str) -> list[str]:
    """Split a markdown row on unescaped pipes."""
    cells, cur, i = [], "", 0
    while i < len(rest):
        c = rest[i]
        if c == "\\" and i + 1 < len(rest) and rest[i + 1] == "|":
            cur += "|"
            i += 2
            continue
        if c == "|":
            cells.append(cur.strip())
            cur = ""
        else:
            cur += c
        i += 1
    cells.append(cur.strip())
    return cells


def parse() -> list[tuple[str, str, str, str, str, str]]:
    rows = []
    for line in SPEC.read_text(encoding="utf-8").splitlines():
        m = ROW.match(line)
        if not m:
            continue
        code, kind = m.group(1), m.group(2).strip()
        cells = split_cells(m.group(3))
        meaning, what, why, try_ = (cells + ["", "", "", ""])[:4]
        rows.append((code, kind, meaning, what, why, try_))
    return rows


def render(rows: list[tuple[str, str, str, str, str, str]]) -> str:
    out = [
        '"""Error registry, generated from spec/14-errors.md by tools/gen_codes.py.',
        "",
        "Do not edit by hand. Kinds: E compile error, W warning, P panic, H host refusal.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "# code: (kind, meaning, what, why, try)",
        "CODES: dict[str, tuple[str, str, str, str, str]] = {",
    ]
    for code, kind, meaning, what, why, try_ in rows:
        out.append(f"    {('SAY-' + code)!r}: (")
        for v in (kind, meaning, what, why, try_):
            out.append(f"        {v!r},")
        out.append("    ),")
    out.append("}")
    out.append("")
    out.append('RETIRED = frozenset(c for c, v in CODES.items() if v[0] in ("\\u2014", "-"))')
    out.append("ACTIVE = frozenset(c for c in CODES if c not in RETIRED)")
    out.append("")
    return "\n".join(out)


def main() -> int:
    text = render(parse())
    if "--check" in sys.argv:
        if OUT.read_text(encoding="utf-8") != text:
            print("codes.py is out of date; run python tools/gen_codes.py")
            return 1
        return 0
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(parse())} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
