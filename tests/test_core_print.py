"""Printers, lowering, SCS-1 and hashing (M3): LOW rows, HASH-01..12, G-01 text, FMT rules.
Spec: spec/04-core-ast.md sections 3-6, spec/13-tooling.md section 2."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

from sayform import core as C
from sayform.diagnostics import SayError
from sayform.parser import parse
from sayform.printer import print_module
from sayform.scs import Encoder, hash_module, serialise, show_hash

ROOT = Path(__file__).resolve().parents[1]
HEAD = "edition 0\nneeds console\n\n"
PRE = (
    "a Person has a name (text) and an age (an integer), changeable\n\n"
    "to copy from src to dst:\n    give back src\n\n"
    "to main, needs console:\n"
    '    let p be Person with name "Ada" and age 36\n'
    "    let xs be [3, 1, 2]\n    let n be 2, changeable\n    let e be quote (n)\n"
)


def body(stmts: str) -> tuple[object, ...]:
    m = parse(HEAD + PRE + "".join("    " + ln + "\n" for ln in stmts.splitlines()))
    return m.body[-1].body.stmts[4:]  # type: ignore[attr-defined, no-any-return]


# LOW: every listed spelling of a lowering row yields the identical core (04 section 3).
LOW = [
    ("let x be 1", "let x = 1"),
    ("let x be 1, changeable", "var x = 1"),
    ("set n to 3", "n := 3"),
    ("add 1 to n", "n += 1"),
    ("change the age of p to 37", "p.age := 37"),
    (
        "if n equals 1:\n    show 1\notherwise if n equals 2:\n    show 2\notherwise:\n    show 3",
        "if n = 1:\n    show(1)\nelif n == 2:\n    show(2)\nelse:\n    show(3)",
    ),
    ("for each x in xs:\n    show x", "for x in xs:\n    show(x)"),
    ("repeat 3 times:\n    show 1", "for _ in 1..3:\n    show(1)"),
    ("while n is less than 3:\n    stop", "while n < 3:\n    break"),
    ("for each x in xs:\n    skip", "for x in xs:\n    continue"),
    ("show 12.50", "show(12.50)"),
    ("show yes", "show(true)"),
    ("show no", "show(false)"),
    ('show "Hi {n}"', 'show("Hi {n}")'),
    ("show the symbol x", "show('x)"),
    ("show p's name", "show(p.name)"),
    ("show the name of p", "show(p.name)"),
    ("show p's name, if any", "show(p?.name)"),
    ("show item 1 of xs", "show(xs[1])"),
    ("show item 1 of xs, if any", "show(xs?[1])"),
    ("show count of xs", "show(count(xs))"),
    ("let r be xs then count", "let r = xs |> count"),
    ("let f be given x, x plus 1", "let f = x => x + 1"),
    ('show Person with name "B" and age 1', 'show(Person(name="B", age=1))'),
    ("let q be p with age 37", "let q = p.with(age=37)"),
    ("show (n is a number)", "show(n is Number)"),
    ("show (try n)", "show(n?)"),
    ("show quote (n plus 1)", "show(`(n + 1))"),
    ("show the type a list of numbers", "show(List[Number])"),
    ("show (n plus 1 minus 2 times 3)", "show(n + 1 - 2 * 3)"),
    ("show (n divided by 2)", "show(n / 2)"),
    ("show (n divided by 2, rounded down)", "show(n // 2)"),
    ("show (n mod 2)", "show(n % 2)"),
    ("show (n to the power of 2)", "show(n ^ 2)"),
    ("show negative n", "show(-n)"),
    ("show (n equals 1)", "show(n == 1)"),
    ("show (n is not equal to 1)", "show(n != 1)"),
    ("show (n is at most 1)", "show(n <= 1)"),
    ("show (n is at least 1)", "show(n >= 1)"),
    ("show (n is between 1 and 3, exclusive)", "show(1 < n < 3)"),
    ("show (n is between 1 and 3)", "show(3 >= n >= 1)"),
    ("show (not yes)", "show(!yes)"),
    ("show (yes and no)", "show(yes && no)"),
    ("show (yes or no)", "show(yes || no)"),
    ("show (n is in xs)", "show(xs contains n)"),
    ("show (n is in xs)", "show(n in xs)"),
    ("show (n is the same as n)", "show(n === n)"),
    ("show (xs is empty)", "show(is_empty(xs))"),
    ('show ("a" joined with "b")', 'show("a" ++ "b")'),
    ('show (xs joined by ", ")', 'show(join_all(xs, ", "))'),
    ("show (xs each it plus 1)", "show(map(xs, it => it + 1))"),
    ("show each x in xs, x plus 1", "show(map(xs, x => x + 1))"),
    ("show (xs where it is at least 2)", "show(filter(xs, it => it >= 2))"),
    ("show (xs sorted)", "show(sort(xs))"),
    ("show (xs sorted by it, descending)", "show(sort_by(xs, it => it, descending=yes))"),
    ("show (xs grouped by it)", "show(group_by(xs, it => it))"),
    ("show (from 1 to 9 by 2)", "show(1..9 by 2)"),
    ("show (from 1 up to 9)", "show(1..<9)"),
    ("show (nothing or else 1)", "show(nothing ?? 1)"),
    ("show problem missing", "show(problem('missing))"),
    ("show evaluate e with bindings {}", "show(evaluate(e, bindings={}))"),
    ("show (e matches quote (?a))", "show(e ~= `(?a))"),
    ("copy from 1 to 2", "copy(from=1, to=2)"),
]


@pytest.mark.parametrize("words,symbols", LOW, ids=[f"LOW-{i + 1:02d}" for i in range(len(LOW))])
def test_low_rows_same_core(words: str, symbols: str) -> None:
    assert body(words) == body(symbols)


def h(src: str) -> tuple[dict[str, bytes], bytes]:
    return hash_module(parse(HEAD + src))


def test_hash_01_words_and_symbols_equal() -> None:
    w = "to add-one of x (a number) giving a number:\n    give back x plus 1\n"
    s = "def add_one(of x: Number) -> Number:\n    return x + 1\n"
    assert h(w)[1] == h(s)[1]


def test_hash_02_rename_local() -> None:
    a = h("to f x:\n    let y be x plus 1\n    give back y\n")[0]["f"]
    b = h("to f z:\n    let w be z plus 1\n    give back w\n")[0]["f"]
    assert a == b


def test_hash_03_rename_function() -> None:
    assert h("to f x:\n    give back f(x)\n")[0]["f"] == h("to g x:\n    give back g(x)\n")[0]["g"]


@pytest.mark.parametrize(
    "a,b",
    [
        ("a P has a size (a number)\n", "a P has a width (a number)\n"),
        ("a P has a size (a number)\n", "a Q has a size (a number)\n"),
        ("to f to x:\n    give back x\n", "to f into x:\n    give back x\n"),
        ("a S is one of:\n    dot\n", "a S is one of:\n    spot\n"),
    ],
)
def test_hash_04_rename_interface_changes_hash(a: str, b: str) -> None:
    assert list(h(a)[0].values()) != list(h(b)[0].values())


def test_hash_05_comments_and_notes() -> None:
    a = h("to f:\n    give back 1\n")
    b = h("# hi\nnote: about f\nto f:\n    give back 1  # one\n")
    assert a == b


def test_hash_06_decimal_scale() -> None:
    assert h("to f:\n    give back 12.50\n")[0]["f"] != h("to f:\n    give back 12.5\n")[0]["f"]
    assert C.Lit("decimal", __import__("decimal").Decimal("12.50")).value == __import__("decimal").Decimal("12.5")


def test_hash_07_merkle() -> None:
    a = h("to g:\n    give back 1\n\nto f:\n    give back g()\n")[0]["f"]
    b = h("to g:\n    give back 2\n\nto f:\n    give back g()\n")[0]["f"]
    assert a != b


def test_hash_08_scc_deterministic() -> None:
    src = "to even n:\n    give back odd(n)\n\nto odd n:\n    give back even(n)\n"
    src2 = "to odd n:\n    give back even(n)\n\nto even n:\n    give back odd(n)\n"
    assert h(src) == h(src) and h(src)[1] == h(src2)[1]


def test_hash_09_export_rename_changes_module_hash() -> None:
    assert h("to f:\n    give back 1\n")[1] != h("to g:\n    give back 1\n")[1]


def test_hash_10_printed_form() -> None:
    assert re.fullmatch(r"b3:[a-z2-7]{52}", show_hash(h("to f:\n    give back 1\n")[1]))


VECTORS = [
    C.Lit("integer", 0), C.Lit("integer", 300), C.Lit("decimal", __import__("decimal").Decimal("12.50")),
    C.Lit("approx", -0.0), C.Lit("text", "héllo"), C.Lit("truth", True), C.SymLit("total-cost"),
    C.Call(C.Name("add", C.Ref("builtin", "add")), (C.Name("x", C.Ref("local", 0)), C.Lit("integer", 1))),
    C.ListLit((C.Lit("nothing", None),)), C.Get(C.Name("p", C.Ref("local", 1)), "name", True),
]  # fmt: skip


def test_hash_11_vectors() -> None:
    data = tomllib.loads((ROOT / "conformance" / "hash" / "vectors.toml").read_text(encoding="utf-8"))
    assert [serialise(v).hex() for v in VECTORS] == [x["scs"] for x in data["vector"]]


def test_hash_12_unknown_tag() -> None:
    class Strange(C.Node):
        pass

    with pytest.raises(SayError) as e:
        Encoder().node(Strange())
    assert e.value.code == "SAY-E1002"


G01_WORDS = 'module hello\nedition 0\nneeds console\n\n\nto main, needs console:\n    show "Hello, world"\n'
G01_SYMBOLS = 'module hello\nedition 0\nneeds console\n\n\ndef main() needs console:\n    show("Hello, world")\n'


def test_g01_canonical_prints() -> None:
    m = parse(G01_SYMBOLS, name="hello")
    assert print_module(m, "words") == G01_WORDS
    assert print_module(parse(G01_WORDS, name="hello"), "symbols") == G01_SYMBOLS


@pytest.mark.parametrize(
    "src,words,symbols",
    [
        (
            "to main:\n    if 1 = 1 and 2 == 2:\n        stop_it()\n",
            "1 equals 1 and 2 equals 2",
            "1 = 1 && 2 = 2",
        ),  # F-R3/R4
        ("to main:\n    let x be 1.\n", "let x be 1", "let x = 1"),  # F-R12
        ("to main:\n    let total_cost be 1\n", "let total-cost be 1", "let total_cost = 1"),  # F-R13
        (
            "to main:\n    show(count(xs where it > 1))\n",
            "count of (xs where it is greater than 1)",
            "count(filter(",
        ),  # F-R8
        ("to main:\n    let r be yes and no or yes\n", "(yes and no) or yes", "(yes && no) || yes"),  # F-R8/R15
        ("to main:\n    for _ in 1..3:\n        show(1)\n", "repeat 3 times:", "for _ in 1..3:"),  # F-R16
        ("to main:\n    show(1 <= 2 < 3)\n", "2 is between 1 and 3, exclusive above", "1 <= 2 < 3"),  # F-R15
    ],
)
def test_fmt_rules(src: str, words: str, symbols: str) -> None:
    m = parse("edition 0\nneeds console\n\nlet xs be [1]\n\n" + src.replace("stop_it()", "show(1)"))
    assert words in print_module(m, "words")
    assert symbols in print_module(m, "symbols")
