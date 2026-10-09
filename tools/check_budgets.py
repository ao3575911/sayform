"""Fail if any hard budget (spec 01 section 5, spec 17 K6) is exceeded.

Counts reserved and contextual words, core node classes, builtins, runtime dependencies
and interpreter lines (excluding generated tables). Prints one line per budget.
"""

from __future__ import annotations

import inspect
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sayform import codes, core, keywords, lower  # noqa: E402

GENERATED = {"codes.py"}
LIMITS = {
    "reserved words": 63,
    "contextual words": 89,
    "core nodes": 44,
    "core nodes (v0)": 40,
    "type sub-nodes": 9,
    "pattern sub-nodes": 9,
    "precedence levels": 16,
    "builtins": 74,
    "host primitives": 53,
    "prelude functions": 21,
    "error codes (active)": 96,
    "runtime dependencies": 2,
    "interpreter lines": 8000,
}
V01_NODES = {"RoleDef", "Plays", "EffectDef", "OperatorDef"}


def measure() -> dict[str, int]:
    tagged = [
        c for c in vars(core).values() if inspect.isclass(c) and issubclass(c, core.Node) and c.TAG
    ]
    nodes = [c for c in tagged if c.TAG <= 44]
    lines = 0
    for p in (ROOT / "src" / "sayform").rglob("*.py"):
        if p.name in GENERATED or "_unicode" in p.parts:
            continue
        lines += sum(1 for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip())
    deps = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["dependencies"]
    return {
        "reserved words": len(set(keywords.RESERVED)),
        "contextual words": len(set(keywords.CONTEXTUAL)),
        "core nodes": len(nodes),
        "core nodes (v0)": len([c for c in nodes if c.__name__ not in V01_NODES]),
        "type sub-nodes": len([c for c in tagged if 60 <= c.TAG <= 68]),
        "pattern sub-nodes": len([c for c in tagged if 70 <= c.TAG <= 78]),
        "precedence levels": len(lower.PRECEDENCE),
        "builtins": len(lower.HOST_SIGS) + len(lower.PRELUDE_NAMES),
        "host primitives": len(lower.HOST_SIGS),
        "prelude functions": len(lower.PRELUDE_NAMES),
        "error codes (active)": len(codes.ACTIVE),
        "runtime dependencies": len(deps),
        "interpreter lines": lines,
    }


def main() -> int:
    exact = {
        "reserved words",
        "contextual words",
        "core nodes",
        "core nodes (v0)",
        "type sub-nodes",
        "pattern sub-nodes",
        "precedence levels",
        "builtins",
        "host primitives",
        "prelude functions",
        "error codes (active)",
    }
    bad = 0
    for name, value in measure().items():
        limit = LIMITS[name]
        ok = value == limit if name in exact else value <= limit
        bad += not ok
        print(
            f"{'ok  ' if ok else 'FAIL'} {name}: {value} ({'=' if name in exact else '<='} {limit})"
        )
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
