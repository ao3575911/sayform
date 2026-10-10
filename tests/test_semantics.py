"""Values and evaluator (M4): NUM, TXT, REC, COL, TYP, SEM, PAT, ERRV, DSP, OPT rows.
Spec: spec/05-types-values.md, spec/06-operators.md, spec/07-semantics.md; IDs from spec/15-conformance.md."""

from __future__ import annotations

import pytest
from runner import run, run_source, shows

PERSON = (
    "a Person (plural people) has a name (text) and an age (an integer, default 0), where age is at least 0\n\n"
    "a Counter has a value (an integer), changeable\n\n"
    "a Shape is one of:\n    circle with a radius (a number)\n"
    "    rectangle with a width (a number) and a height (a number)\n    dot\n"
)

OUT = [
    # numbers (spec 05 section 3)
    ("NUM-01", "show (0.1 + 0.2 equals 0.3)", ["yes"]),
    ("NUM-02", "show 1 / 4", ["0.25"]),
    ("NUM-03", "show 1 / 3", ["1/3"]),
    ("NUM-04", "show 1.50 + 2.250\nshow 1.5 * 0.10\nshow 2 * 3\nshow 2 + 0.5", ["3.750", "0.150", "6", "2.5"]),
    ("NUM-05", "show -7 // 2\nshow 7 // 2", ["-4", "3"]),
    ("NUM-06", "show (negative 7) mod 3\nshow 7 mod -3", ["2", "-2"]),
    ("NUM-07", "show 2 ^ -1", ["0.5"]),
    ("NUM-08", "show 0 ^ 0\nshow 2 ^ 3 ^ 2", ["1", "512"]),
    ("NUM-12", "show approx 0.1 + approx 0.2\nshow 1 + approx 0.5", ["approx 0.30000000000000004", "approx 1.5"]),
    ("NUM-13", "show (0.1 equals approx 0.1)\nshow (1 equals approx 1.0)", ["no", "yes"]),
    ("NUM-14", "show round 2.5\nshow round 3.5\nshow round 2.675 with places 2\nshow round 2.5 with mode 'half-up",
     ["2", "4", "2.68", "3"]),
    ("NUM-15", "show 2 ^ 200 + 1", [str(2**200 + 1)]),
    ("NUM-17", "show (1 equals 1.0)\nshow (12.50 equals 12.5)\nshow 12.50", ["yes", "yes", "12.50"]),
    ("NUM-18", "show 2 / 1\nshow 1.0 / 2\nshow 3 / 8", ["2", "0.5", "0.375"]),
    ("NUM-19", "show 1/3 + 1/6", ["0.5"]),
    ("NUM-20", "show checked-divide 1 by 0 or else 99\nshow checked-divide 1 by 4", ["99", "0.25"]),
    # text (spec 05 section 4)
    ("TXT-01", 'show length of "e\\u{301}"', ["1"]),
    ("TXT-02", 'show length of "👩\\u{200D}👩\\u{200D}👧"\nshow length of "🇦🇺"', ["1", "1"]),
    ("TXT-03", 'show code-points of "é"\nshow utf8-bytes of "é"', ["[233]", "[195, 169]"]),
    ("TXT-04", 'show ("a" is less than "b")\nshow ("Z" is less than "a")', ["yes", "yes"]),
    ("TXT-05", 'let n be 3\nshow "n is {n}, half {n / 2}"', ["n is 3, half 1.5"]),
    ("TXT-06", 'show uppercase of "straße"\nshow trim("  hi ")', ["STRASSE", "hi"]),
    ("TXT-07", 'show split("a,b,,c", by: ",")'.replace("by: ", "by="), ['["a", "b", "", "c"]']),
    ("TXT-08", 'show "a" joined with "b"\nshow count of "héllo"', ["ab", "5"]),
    ("TXT-09", 'show parse-number("12.50")\nshow parse-number("x1") or else 0', ["12.50", "0"]),
    ("TXT-10", 'show ["a", "b"]\nshow "q\\"x"', ['["a", "b"]', 'q"x']),
    # records and variants (spec 05 section 5)
    ("REC-01", 'let p be try (Person with name "Ada" and age 36)\nshow p', ['Person with name "Ada" and age 36']),
    ("REC-02", 'let p be try (Person with name "Bo")\nshow p\'s age', ["0"]),
    ("REC-04", 'let p be try (Person with name "Ada" and age 36)\nlet q be try (p with age 37)\nshow q\'s age\nshow p\'s age',
     ["37", "36"]),
    ("REC-05", 'let r be Person with name "X" and age -1\nshow r', ["problem invalid: Person must satisfy: age is at least 0"]),
    ("REC-06", "let c be Counter with value 1\nchange the value of c to 2\nshow c's value", ["2"]),
    ("REC-07", 'show (try (Person with name "A") equals try (Person with name "A"))\nshow (circle with radius 1 equals dot)',
     ["yes", "no"]),
    ("REC-08", "show circle with radius 2\nshow dot", ["circle with radius 2", "dot"]),
    ("REC-09", "let s be rectangle with width 2 and height 3\nshow s's width", ["2"]),
    # collections (spec 05 section 6)
    ("COL-01", "let xs be [10, 20, 30]\nshow item 1 of xs\nshow xs[-1]", ["10", "30"]),
    ("COL-02", "let xs be [10, 20, 30, 40]\nshow xs[2..3]\nshow xs[2..<4]", ["[20, 30]", "[20, 30]"]),
    ("COL-05", "let xs be [1]\nshow item 5 of xs, if any", ["nothing"]),
    ("COL-06", 'let m be {"a": 1, "b": 2}\nshow m["b"]\nshow m?["z"]\nshow keys of m', ["2", "nothing", '["a", "b"]']),
    ("COL-07", "show ({1, 2} equals {2, 1})\nshow ({\"a\": 1, \"b\": 2} equals {\"b\": 2, \"a\": 1})", ["yes", "yes"]),
    ("COL-08", "show added([1], 2)\nshow added({1}, 1)\nshow added({\"a\": 1}, {\"b\": 2})", ["[1, 2]", "{1}", '{"a": 1, "b": 2}']),
    ("COL-09", "let xs be [], changeable\nadd 3 to xs\nadd 4 to xs\nshow xs", ["[3, 4]"]),
    ("COL-10", "show {}\nshow empty-set\nshow [1, 2] joined with [3]", ["{}", "empty-set", "[1, 2, 3]"]),
    ("COL-11", "show (2 is in [1, 2])\nshow (\"ell\" is in \"hello\")\nshow (3 is not in {1})", ["yes", "yes", "yes"]),
    ("COL-12", "show from 1 to 9 by 3\nshow from 5 to 1\nshow from 1 up to 3", ["[1, 4, 7]", "[]", "[1, 2]"]),
    # semantics (spec 07)
    ("SEM-01", 'to f x:\n    show "f {x}"\n    give back x\nto main2:\n    give back 0',
     None),
    ("SEM-02", "show (no and (1 / 0 equals 1))\nshow (yes or (1 / 0 equals 1))", ["no", "yes"]),
    ("SEM-04", "let x be 1\nif yes:\n    let x be 2\n    show x\nshow x", ["2", "1"]),
    ("SEM-05", "let n be 0, changeable\nwhile n is less than 3:\n    add 1 to n\nshow n", ["3"]),
    ("SEM-06", "for each x in [1, 2, 3, 4]:\n    if x equals 2:\n        skip\n    if x equals 4:\n        stop\n    show x", ["1", "3"]),
    ("SEM-07", "repeat 2 times:\n    show 1", ["1", "1"]),
    ("SEM-08", "let f be given x, x * 2\nshow f(4)\nshow [1, 2] each it + 1", ["8", "[2, 3]"]),
    ("SEM-09", "let n be 1, changeable\nlet f be given x, x + n\nset n to 10\nshow f(1)", ["11"]),
    ("SEM-10", "show 1 then negate", ["-1"]),
    ("SEM-11", "show [3, 1, 2] sorted\nshow [3, 1, 2] where it is at least 2\nshow sum of [1, 2.5]", ["[1, 2, 3]", "[3, 2]", "3.5"]),
    ("SEM-12", 'show ["bb", "a", "ccc"] sorted by length of it, descending', ['["ccc", "bb", "a"]']),
    ("SEM-13", 'show ["ab", "b", "ac"] grouped by count of it', ['{2: ["ab", "ac"], 1: ["b"]}']),
    # patterns (spec 07 section 5)
    ("PAT-01", "match 3:\n    when 1:\n        show 1\n    when from 2 to 5:\n        show 25\n    otherwise:\n        show 0", ["25"]),
    ("PAT-02", "match [1, 2, 3]:\n    when [?a1, and more ?rest]:\n        show rest\n", None),
    ("PAT-03", "let s be circle with radius 2\nmatch s:\n    when circle with radius ?r, if r is greater than 5:\n"
     "        show 1\n    when circle with radius ?r:\n        show r\n    otherwise:\n        show 0", ["2"]),
    ("PAT-04", "match dot:\n    when circle with radius ?r or rectangle with width ?r, and more:\n        show r\n"
     "    when dot:\n        show 9", ["9"]),
    # problems (spec 07 section 6)
    ("ERRV-01", "show problem not-found with message \"no such city\"", ["problem not-found: no such city"]),
    ("ERRV-02", "show nothing or else 5\nshow 0 or else 5\nshow (problem invalid) or else 6", ["5", "0", "6"]),
    ("ERRV-03", 'let p be problem invalid\nshow p\'s kind', ["'invalid"]),
]  # fmt: skip


def sh(body: str) -> str:
    """Bracket the argument of every `show` line so R6 never splits an operator off it."""
    out = []
    for ln in body.splitlines():
        pre = ln[: len(ln) - len(ln.lstrip())]
        out.append(f"{pre}show ({ln.strip()[5:]})" if ln.strip().startswith("show ") else ln)
    return "\n".join(out)


@pytest.mark.parametrize("tid,body,expected", [x for x in OUT if x[2] is not None], ids=[x[0] for x in OUT if x[2]])
def test_output(tid: str, body: str, expected: list[str]) -> None:
    assert shows(sh(body), PERSON) == expected


ERR = [
    ("NUM-09", "show (negative 8) ^ (1/3)", "SAY-E0842", 70),
    ("NUM-10", "show 1 / 0", "SAY-E0841", 70),
    ("NUM-16", "show [1, 2][approx 1.0]", "SAY-E0801", 70),
    ("NUM-21", "show 0 ^ -1", "SAY-E0841", 70),
    ("NUM-22", "show 5 // 0", "SAY-E0841", 70),
    ("NUM-23", "show from 1 to 5 by 0", "SAY-E0802", 70),
    ("COL-03", "let i be 0\nshow [1][i]", "SAY-E0831", 70),
    ("COL-04", "show [1][2]", "SAY-E0832", 70),
    ("COL-13", 'show {"a": 1}["b"]', "SAY-E0832", 70),
    ("COL-14", 'show [1, "a"] sorted', "SAY-E0803", 70),
    ("TXT-11", 'let n be 1\nshow "a" joined with n', "SAY-E0202", 70),
    ("REC-10", "let p be Person with age 3\nshow p", "SAY-E0211", 2),
    ("REC-11", "let c be dot\nchange the value of c to 2", "SAY-E0303", 2),
    ("SEM-20", "if 1:\n    show 1", "SAY-E0212", 70),
    ("SEM-21", "let x be 1\nshow not x", "SAY-E0212", 70),
    ("PAT-10", "match 7:\n    when 1:\n        show 1", "SAY-E0212", 70),
    ("ERRV-05", "show (1 or 2)", "SAY-E0212", 70),
]


@pytest.mark.parametrize("tid,body,code,exit", ERR, ids=[x[0] for x in ERR])
def test_errors(tid: str, body: str, code: str, exit: int) -> None:
    r = run(sh(body), PERSON)
    assert (r.code, r.exit) == (code, exit), r.what


def test_sem_call_depth_limit() -> None:
    r = run("show f(1)", "to f n:\n    give back f(n + 1)\n")
    assert (r.code, r.exit) == ("SAY-E0212", 70) and "this call" in r.what


def test_sem_depth_1000_supported() -> None:
    assert shows("show f(1000)", "to f n:\n    if n equals 0:\n        give back 0\n    give back 1 + f(n - 1)\n") == [
        "1000"
    ]


def test_sem_evaluation_order_and_defaults() -> None:
    header = 'to f x, needs console:\n    show "f {x}"\n    give back x\n\nto g a1 with k (a number, default f(9)), needs console:\n    give back a1 + k\n'
    assert shows("show (f(1) + f(2))\nshow g(1)\nshow g(1, k=2)", header) == ["f 1", "f 2", "3", "f 9", "10", "3"]


def test_errv_try_returns_problem_and_main_exit_1() -> None:
    header = (
        "to f x, may fail with invalid:\n    if x equals 0:\n        give back problem invalid\n    give back x\n\n"
    )
    header += "to g x, needs console, may fail with invalid:\n    let y be try f(x)\n    show y\n    give back y\n"
    assert shows("show (g(1) or else 7)\nshow (g(0) or else 7)", header) == ["1", "1", "7"]
    src = "edition 0\nneeds console\n\nto main, needs console, may fail with invalid:\n    give back problem invalid\n"
    assert run_source(src).exit == 1


def test_errv_undeclared_kind_panics() -> None:
    r = run("show f(1)", "to f x:\n    give back problem invalid\n")
    assert (r.code, r.exit) == ("SAY-E0207", 70)


DISPATCH = (
    "a Vector has an x (a number) and a y (a number)\n\n"
    "to add u (a Vector) v (a Vector) giving a Vector:\n    give back Vector with x (u's x + v's x) and y (u's y + v's y)\n\n"
    'to describe v (a number):\n    give back "number"\n\n'
    'to describe v (an integer):\n    give back "integer"\n\n'
    'to describe v (text):\n    give back "text"\n'
)


def test_dsp_multiple_dispatch_most_specific() -> None:
    body = 'show describe(1)\nshow describe(1.5)\nshow describe("a")\nshow ((Vector with x 1 and y 2) + (Vector with x 3 and y 4))\nshow (1 + 2)'
    assert shows(body, DISPATCH) == ["integer", "number", "text", "Vector with x 4 and y 6", "3"]


def test_dsp_no_method() -> None:
    r = run("show describe(yes)", DISPATCH)
    assert (r.code, r.exit) == ("SAY-E0212", 70)


def test_dsp_e0402_equal_methods() -> None:
    r = run("show 1", "to f v (text):\n    give back 1\n\nto f w (text):\n    give back 2\n")
    assert r.code == "SAY-E0402"
