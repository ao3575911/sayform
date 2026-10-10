"""Symbolic core (M7): SYM-01..SYM-23 and G-08 (spec/08-symbolic.md)."""

from __future__ import annotations

from runner import run, shows

from sayform.evaluator import program
from sayform.parser import parse

ALGEBRA = (
    "ruleset algebra:\n    rewrite ?a + 0 as ?a\n    rewrite ?a * 1 as ?a\n    rewrite ?a * 0 as 0\n\n"
    "ruleset distribute:\n    rewrite ?a * (?b + ?c) as ?a * ?b + ?a * ?c\n    rewrite ?a + 0 as ?a\n\n"
    "ruleset loop:\n    rewrite ?a + ?b as ?b + ?a\n\n"
    "ruleset small:\n    rewrite ?a * ?b as ?b * ?a when ?a is a number\n"
)


def test_sym_01_symbols() -> None:
    assert shows("show ('read_csv equals the symbol read-csv)\nshow 'x") == ["yes", "'x"]


def test_sym_02_quote_is_unevaluated() -> None:
    assert shows("show quote (x + y * 2)\nshow (quote (1 + 1) is an expression)") == ["x + y * 2", "yes"]


def test_sym_03_04_unquote() -> None:
    body = "let e be quote (y + 1)\nlet n be 3\nshow quote (x * ~e)\nshow quote (x * (~n + 0))"
    assert shows(body) == ["x * (y + 1)", "x * (3 + 0)"]


def test_sym_05_unquote_outside_quote() -> None:
    assert run("let n be 1\nshow ~n").code == "SAY-E0901"


def test_sym_06_nested_quote() -> None:
    assert shows("show quote (quote (x))") == ["`(x)"]


def test_sym_07_head_and_arguments() -> None:
    body = "let e be quote (f(1, x) + 2)\nshow head of e\nshow arguments of e\nshow head of quote (f(1))"
    assert shows(body) == ["'add", "[f(1, x), 2]", "'f"]


def test_sym_08_evaluate_with_bindings() -> None:
    assert shows("show evaluate quote (x * 2 + 1) with bindings {'x: 5}") == ["11"]


def test_sym_09_evaluate_unbound() -> None:
    assert shows("show ((evaluate quote (x + 1)) is a problem)") == ["yes"]


def test_sym_10_evaluate_effect_without_capability() -> None:
    r = run('show 1\nlet e be quote (show("x"))\nlet f be given q, evaluate q\nshow f(e)', needs="console")
    assert r.out == ["1", "x", "nothing"]
    header = "to quiet e:\n    give back evaluate e\n"
    r = run('show quiet(quote (show("x")))', header)
    assert (r.code, r.exit) == ("SAY-E0503", 70)


def test_sym_11_rules_not_applied_implicitly() -> None:
    assert shows("show quote (x + 0)", ALGEBRA) == ["x + 0"]


def test_sym_12_template_unknown_variable() -> None:
    assert run("show 1", "ruleset bad:\n    rewrite ?a + 0 as ?b\n").code == "SAY-E0902"


def test_sym_13_rule_outside_ruleset() -> None:
    assert run("show 1", "rewrite ?a + 0 as ?a\n").code == "SAY-E0903"


def test_sym_14_repeated_pattern_variable() -> None:
    header = "ruleset same:\n    rewrite ?a - ?a as 0\n"
    assert shows("show simplify quote (x - x) using same\nshow simplify quote (x - y) using same", header) == [
        "0",
        "x - y",
    ]


def test_sym_15_simplify() -> None:
    assert shows("show simplify quote (x * (y + 0)) using algebra", ALGEBRA) == ["x * y"]


def test_sym_16_distribution_unique_minimum() -> None:
    assert shows("show simplify quote (x * (y + 0)) using distribute", ALGEBRA) == ["x * y"]


def test_sym_17_budget_best_so_far() -> None:
    r = run("show simplify quote (x + y) using loop", ALGEBRA)
    assert r.exit == 0 and r.out == ["x + y"]
    src = f"edition 0\nneeds console\n\n{ALGEBRA}\n\nto main, needs console:\n    show simplify quote (x + y) using loop\n"
    ev, _ = program(parse(src), lambda t, end="\n": None)
    assert [w.code for w in ev.warnings] == ["SAY-W0912"]


def test_sym_18_tie_break_by_scs1() -> None:
    assert shows("show simplify quote (2 * x) using small", ALGEBRA) in (["2 * x"], ["x * 2"])


def test_sym_19_20_21_equivalence() -> None:
    body = (
        "show ((quote (x + 0)) is equivalent to quote (x) using algebra)\n"
        "show ((quote (x + 1)) is equivalent to quote (x) using algebra)\n"
        "show ((quote (x + y)) is equivalent to quote (y + x + 0) using loop)"
    )
    assert shows(body, ALGEBRA) == ["yes", "no", "nothing"]


def test_sym_22_23_matches() -> None:
    body = (
        "show (quote (2 * (y + 1)) matches quote (?p * (?q + ?r)))\n"
        "show (quote (2 + 1) matches quote (?p * ?q))\n"
        "match quote (2 * (y + 1)):\n    when quote (?p * ?q):\n        show q"
    )
    assert shows(body) == ["{'p: 2, 'q: y, 'r: 1}", "nothing", "y + 1"]


def test_g08_algebra_demo() -> None:
    body = (
        "let e be quote (x * (y + 0) * 1)\nshow simplify e using algebra\n"
        "let proven be (quote (x + 0)) is equivalent to quote (x) using algebra\nshow proven"
    )
    assert shows(body, ALGEBRA) == ["x * y", "yes"]
