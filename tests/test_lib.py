"""Standard library (M6): `LIB-<name>` for host primitives and `LIB-PRELUDE-SAY` (spec/12-stdlib.md).
Symbolic and task primitives get their LIB rows with M7 and M8."""

from __future__ import annotations

from pathlib import Path

import pytest
from runner import run, shows

from sayform.evaluator import run_checks
from sayform.parser import parse

ROOT = Path(__file__).resolve().parents[1]

LIB = [
    ("equal", ['show (equal(1, 1.0))', 'show (equal("a", 1))', "show (equal([1, [2]], [1, [2]]))"], ["yes", "no", "yes"]),
    ("same", ["show ([1] is the same as [1])"], ["yes"]),
    ("not", ["show (not no)"], ["yes"]),
    ("and", ["show (yes and no)"], ["no"]),
    ("or", ["show (no or yes)"], ["yes"]),
    ("default", ["show (nothing or else 1)", "show (no or else 1)"], ["1", "no"]),
    ("problem", ['show problem(\'x, message="m")\'s message'], ["m"]),
    ("display", ['show display of [1, "a", yes, nothing]', "show display of (1 / 3)"], ['[1, "a", yes, nothing]', "1/3"]),
    ("show", ['show "a{1}b"'], ["a1b"]),
    ("add", ["show (1 + 2.0)"], ["3.0"]),
    ("subtract", ["show (1 - 2.50)"], ["-1.50"]),
    ("multiply", ["show (1.5 * 1.5)"], ["2.25"]),
    ("divide", ["show (6 / 4)"], ["1.5"]),
    ("floor-divide", ["show (7.5 // 2)"], ["3"]),
    ("modulo", ["show (7.5 mod 2)"], ["1.5"]),
    ("power", ["show (2 ^ 0.5)"], ["approx 1.4142135623730951"]),
    ("negate", ["show negative 0", "show negative 1.50"], ["0", "-1.50"]),
    ("less", ['show ("abc" is less than "abd")'], ["yes"]),
    ("round", ["show round 1.25 with places 1", "show round (negative 2.5)", "show round (7 / 3) with places 3"],
     ["1.2", "-2", "2.333"]),
    ("length", ['show length of "naïve"'], ["5"]),
    ("uppercase", ['show uppercase of "abc"'], ["ABC"]),
    ("lowercase", ['show lowercase of "ÀB"'], ["àb"]),
    ("join", ['show ("a" joined with "")'], ["a"]),
    ("split", ['show split("a b", by=" ")'], ['["a", "b"]']),
    ("trim", ['show trim("\\t x \\n")'], ["x"]),
    ("code-points", ['show code-points of "ab"'], ["[97, 98]"]),
    ("utf8-bytes", ['show utf8-bytes of "€"'], ["[226, 130, 172]"]),
    ("parse-number", ['show parse-number("-12")', 'show (parse-number("1.") or else "bad")'], ["-12", "bad"]),
    ("range", ["show range(1, 3)", "show range(1, 3, exclusive=yes)", "show range(0, 1, step=0.5)", "show range(3, 1, step=-1)"],
     ["[1, 2, 3]", "[1, 2]", "[0, 0.5, 1.0]", "[3, 2, 1]"]),
    ("added", ["show added({1: 2}, {1: 3})"], ["{1: 3}"]),
    ("count", ['show count of {"a": 1}', "show count of {1, 2}"], ["1", "2"]),
    ("sort-by", ['show ([[2, "b"], [1, "a"], [2, "a"]] sorted by item 1 of it)'], ['[[1, "a"], [2, "b"], [2, "a"]]']),
    ("contains", ['show ("k" is in {"k": 1})', 'show ([1] is in [[1]])'], ["yes", "yes"]),
    ("keys", ['show keys of {"b": 1, "a": 2}'], ['["b", "a"]']),
    ("values", ['show values of {"b": 1, "a": 2}'], ["[1, 2]"]),
]  # fmt: skip


@pytest.mark.parametrize("name,lines,expected", LIB, ids=[f"LIB-{x[0]}" for x in LIB])
def test_lib(name: str, lines: list[str], expected: list[str]) -> None:
    assert shows("\n".join(lines)) == expected


LIB_ERR = [
    ("not", "show (not 1)", "SAY-E0212"),
    ("problem", 'show problem("x")', "SAY-E0212"),
    ("add", 'show ("a" + 1)', "SAY-E0202"),
    ("divide", "show (1 / 0)", "SAY-E0841"),
    ("modulo", "show (1 mod 0)", "SAY-E0841"),
    ("power", "show ((negative 1) ^ 0.5)", "SAY-E0842"),
    ("less", 'show ("a" is less than 1)', "SAY-E0212"),
    ("round", "show round 1 with mode 'up", "SAY-E0212"),
    ("length", "show length of 1", "SAY-E0212"),
    ("join", 'show ("a" joined with 1)', "SAY-E0202"),
    ("split", 'show split("a", by="")', "SAY-E0212"),
    ("range", "show range(1, approx 2.0)", "SAY-E0801"),
    ("added", "show added(1, [1])", "SAY-E0212"),
    ("count", "show count of 5", "SAY-E0212"),
    ("sort-by", 'show ([1, "a"] sorted by it)', "SAY-E0803"),
    ("keys", "show keys of [1]", "SAY-E0212"),
]


@pytest.mark.parametrize("name,line,code", LIB_ERR, ids=[f"LIB-{x[0]}-error" for x in LIB_ERR])
def test_lib_errors(name: str, line: str, code: str) -> None:
    r = run(line)
    assert (r.code, r.exit) == (code, 70), r.what


def test_lib_ask_reads_a_line_and_end_of_input() -> None:
    r = run('show ask("name? ")\nshow (ask("again? ") is a problem)', stdin=["Ada"])
    assert r.out == ["name? ", "Ada", "again? ", "yes"]


def test_lib_prelude_say() -> None:
    """LIB-PRELUDE-SAY / G-14: the 21 Sayform prelude functions pass their own checks."""
    mod = parse((ROOT / "prelude" / "prelude.test.say").read_text(encoding="utf-8"), name="prelude-test")
    results = run_checks(mod)
    assert len(results) >= 35 and all(r.ok for r in results), [r for r in results if not r.ok]
    prelude = (ROOT / "prelude" / "prelude.say").read_text(encoding="utf-8")
    names = {d.name for d in parse(prelude, name="prelude").body if hasattr(d, "params")}
    assert len(names) == 21
