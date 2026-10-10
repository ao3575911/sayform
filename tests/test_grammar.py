"""Grammar and ambiguity conformance GRM-01..GRM-30 (spec/15-conformance.md section 3,
spec/03-grammar.md). Each test checks the core produced by the parser, or the diagnostic."""

from __future__ import annotations

import pytest

from sayform import core as C
from sayform.diagnostics import SayError, Sink
from sayform.parser import parse

HEAD = "edition 0\nneeds console\n\n"


def mod(body: str) -> C.Module:
    return parse(HEAD + body)


def main_of(stmts: str, extra: str = "") -> tuple[object, ...]:
    body = "".join("    " + ln + "\n" for ln in stmts.strip("\n").splitlines())
    m = mod(extra + "to main, needs console:\n" + body)
    fn = [d for d in m.body if isinstance(d, C.Func) and d.name == "main"][0]
    return fn.body.stmts


def value_of(expr: str, extra: str = "", pre: str = "") -> object:
    stmts = main_of(pre + f"let result be {expr}\n", extra)
    bind = stmts[-1]
    assert isinstance(bind, C.Bind)
    return bind.value


def err(src: str) -> SayError:
    with pytest.raises(SayError) as e:
        mod(src)
    return e.value


def err_main(stmts: str, extra: str = "") -> str:
    with pytest.raises(SayError) as e:
        main_of(stmts, extra)
    return e.value.code


def fn_name(call: object) -> str:
    assert isinstance(call, C.Call) and isinstance(call.fn, C.Name)
    return call.fn.name


PEOPLE = "a Person has a name (text) and an age (an integer)\n\n"


def test_grm_01_type_phrase_in_value_position() -> None:
    assert err_main("let numbers be [3, 1]\nlet ranked be a list of numbers sorted by size") == "SAY-E0107"


def test_grm_02_article_outside_slot() -> None:
    assert err_main("let x be a 5") == "SAY-E0104"


def test_grm_03_clauses_chain_left_to_right() -> None:
    v = value_of("xs where it > 0 sorted by it", pre="let xs be [3, 1]\n")
    assert fn_name(v) == "sort-by"
    assert isinstance(v, C.Call) and fn_name(v.args[0]) == "filter"


def test_grm_04_parenthesised_clause_in_where_body() -> None:
    v = value_of("xs where (it's tags where it equals 1) is empty", pre="let xs be [3, 1]\n")
    assert fn_name(v) == "filter"


def test_grm_05_possession_forms_agree() -> None:
    extra = "a Car has an owner (a Person)\n\n" + PEOPLE
    pre = 'let car be Car with owner (Person with name "Ada" and age 36)\n'
    assert value_of("the name of the owner of car", extra, pre) == value_of("car's owner's name", extra, pre)
    assert value_of("car.owner.name", extra, pre) == value_of("car's owner's name", extra, pre)


def test_grm_06_descending_attaches_and_stray_modifier() -> None:
    v = value_of("xs sorted by it, descending", pre="let xs be [3, 1]\n")
    assert isinstance(v, C.Call) and v.slots and v.slots[0][0] == "descending"
    assert err_main("let xs be [3, 1]\nlet y be xs, descending") == "SAY-E0130"


def test_grm_07_r6_ambiguity_reports_both_readings() -> None:
    with pytest.raises(SayError) as e:
        main_of("let xs be [3, 1]\nlet avg be sum of xs / count of xs")
    assert e.value.code == "SAY-E0108"
    r = e.value.diag.readings
    assert r == ["(sum of xs) / count of xs", "sum of (xs / count of xs)"]


def test_grm_08_comparison_ends_prefix_call() -> None:
    stmts = main_of('let xs be [3, 1]\nif count of xs is at least 3:\n    show "many"')
    cond = stmts[-1].branches[0].cond  # type: ignore[attr-defined]
    assert fn_name(cond) == "greater-eq" and fn_name(cond.args[0]) == "count"


def test_grm_09_show_plus() -> None:
    assert err_main("let x be 1\nshow x + 1") == "SAY-E0108"
    stmts = main_of("let x be 1\nshow (x + 1)")
    assert fn_name(stmts[-1].expr.args[0]) == "add"  # type: ignore[attr-defined]


def test_grm_10_slots_and_parenthesised_range() -> None:
    extra = "to copy from src to dst:\n    give back src\n\n"
    stmts = main_of("let p be 1\nlet q be 2\ncopy from p to q", extra)
    call = stmts[-1].expr  # type: ignore[attr-defined]
    assert [k for k, _ in call.slots] == ["from", "to"]
    show = main_of("show (from 1 to 3)")[-1].expr  # type: ignore[attr-defined]
    assert fn_name(show.args[0]) == "range"


def test_grm_11_first_of_call_vs_block() -> None:
    v = value_of("first of xs", pre="let xs be [3, 1]\n")
    assert fn_name(v) == "first"
    stmts = main_of("let r be first of:\n    1\n    2")
    assert isinstance(stmts[-1].value, C.Concurrent)  # type: ignore[attr-defined]
    assert stmts[-1].value.mode == "first"  # type: ignore[attr-defined]


def test_grm_12_in_is_membership_without_units() -> None:
    v = value_of("2 in xs", pre="let xs be [3, 1]\n")
    assert fn_name(v) == "contains"
    assert err("dialect units\n").code == "SAY-E1013"


def test_grm_13_implicit_it_field_and_clash() -> None:
    v = value_of(
        "people where age is at least 18",
        PEOPLE,
        'let people be [Person with name "Ada" and age 36]\n',
    )
    lam = v.args[1]  # type: ignore[attr-defined]
    assert isinstance(lam.body.args[0], C.Get) and lam.body.args[0].field == "age"
    pre = 'let age be 3\nlet people be [Person with name "Ada" and age 36]\n'
    assert err_main(pre + "let r be people where age is at least 18", PEOPLE) == "SAY-E0108"


def test_grm_14_with_construction_named_args_copy() -> None:
    v = value_of('Person with name "Ada" and age 36', PEOPLE)
    assert isinstance(v, C.RecordLit) and v.base is None
    v2 = value_of("p with age 37", PEOPLE, 'let p be Person with name "Ada" and age 36\n')
    assert isinstance(v2, C.RecordLit) and v2.base is not None
    v3 = value_of("round 2.567 with places 2")
    assert isinstance(v3, C.Call) and v3.slots[0][0] == "places"


def test_grm_15_and_in_named_args_vs_logic() -> None:
    extra = "to send m to who with retries (an integer) with timeout (an integer):\n    give back m\n\n"
    stmts = main_of("let m be 1\nlet bob be 2\nsend m to bob with retries 3 and timeout 5", extra)
    call = stmts[-1].expr  # type: ignore[attr-defined]
    assert [k for k, _ in call.slots] == ["to", "retries", "timeout"]
    v = value_of("yes and no")
    assert fn_name(v) == "and"


def test_grm_16_or_else_vs_or() -> None:
    assert fn_name(value_of("nothing or else 1")) == "default"
    assert fn_name(value_of("yes or no")) == "or"


def test_grm_17_comparison_chains() -> None:
    v = value_of("1 < x < 10", pre="let x be 5\n")
    assert fn_name(v) == "between"
    assert v == value_of("x is between 1 and 10, exclusive", pre="let x be 5\n")
    assert err_main("let n be 1\nlet r be n = n = n") == "SAY-E0121"
    assert err_main("let n be 1\nlet r be n < n > n") == "SAY-E0121"


def test_grm_18_mixed_and_or_warns() -> None:
    sink = Sink()
    parse(HEAD + "to main, needs console:\n    let r be yes and no or yes\n", sink=sink)
    assert [d.code for d in sink.items] == ["SAY-W0116"]


def test_grm_19_add_statement_vs_call() -> None:
    stmts = main_of("let total be 0, changeable\nadd 1 to total")
    assert isinstance(stmts[-1], C.Rebind)
    v = value_of("add(1, 2)")
    assert fn_name(v) == "add"


def test_grm_20_rule_arrow_vs_lambda() -> None:
    m = mod("ruleset algebra:\n    ?x + 0 => ?x\n")
    rs = m.body[0]
    assert isinstance(rs, C.Ruleset) and isinstance(rs.rules[0].lhs, C.PQuote)
    assert isinstance(value_of("x => x + 1"), C.Lambda)


def test_grm_21_type_application_is_type_value() -> None:
    v = value_of("List[Number]")
    assert v == C.TypeExpr(C.TApply("list", (C.TName("number"),)))


WORDS_HEAD = "to f x (a number) giving a number, may fail with bad, needs console, for any T:\n    give back x\n"
OTHER_ORDER = "to f x (a number) giving a number, for any T, needs console, may fail with bad:\n    give back x\n"
SYMBOLS_HEAD = "def f[T](x: Number) -> Number needs console fails bad:\n    return x\n"


def test_grm_22_words_header_any_order() -> None:
    assert mod(WORDS_HEAD).body == mod(OTHER_ORDER).body


def test_grm_23_symbols_header_same_core() -> None:
    assert mod(WORDS_HEAD).body == mod(SYMBOLS_HEAD).body


def test_grm_24_record_inline_and_block() -> None:
    block = "a Person has:\n    a name (text)\n    an age (an integer)\n"
    assert mod(PEOPLE).body == mod(block).body
    assert mod(PEOPLE).body == mod("record Person(name: Text, age: Integer)\n").body


def test_grm_25_variant_words_and_symbols() -> None:
    w = "a Shape is one of:\n    circle with a radius (a number)\n    square with a side (a number)\n"
    s = "variant Shape:\n    circle(radius: Number)\n    square(side: Number)\n"
    assert mod(w).body == mod(s).body


def test_grm_26_match_words_and_symbols() -> None:
    shape = "a Shape is one of:\n    circle with a radius (a number)\n    dot\n\n"
    w = "match s:\n    when circle with radius, if radius > 1:\n        show radius\n    when dot:\n        show 0\n"
    sy = (
        "match s:\n    case circle(radius=?radius) if radius > 1:\n        show radius\n    case dot:\n        show 0\n"
    )
    pre = "let s be dot\n"
    assert main_of(pre + w, shape) == main_of(pre + sy, shape)


def test_grm_27_top_level_statement() -> None:
    e = err('show "hi"\n')
    assert e.code == "SAY-E0130" and "to main" in e.diag.try_


def test_grm_28_positional_after_slot() -> None:
    assert err("to f to dst val:\n    give back dst\n").code == "SAY-E0407"


def test_grm_29_is_adjective() -> None:
    v = value_of("xs is empty", pre="let xs be [1]\n")
    assert fn_name(v) == "is-empty"
    assert err_main("let xs be [1]\nlet r be xs is purple") == "SAY-E0115"
    assert err_main("let xs be [1]\nlet b be 2\nlet r be xs is b") == "SAY-E0110"


@pytest.mark.parametrize(
    "src",
    [
        "role Shape:\n    to area of s giving a number\n",
        "Point plays Show:\n    to display of p:\n        give back 1\n",
        "effect payments\n",
        "dialect money:\n    to f:\n        give back 1\n",
    ],
)
def test_grm_30_v01_declarations(src: str) -> None:
    assert err(src).code == "SAY-E1013"


# ---- parser-level parts of LEX-20 / LEX-21 (spec/02-lexical.md sections 5-6) ----------
@pytest.mark.parametrize("word", [w for w in __import__("sayform.keywords").keywords.RESERVED if w != "'s"])
def test_lex_20_reserved_word_as_name(word: str) -> None:
    assert err_main(f"let {word} be 1") == "SAY-E0109"


@pytest.mark.parametrize(
    "word",
    [w for w in __import__("sayform.keywords").keywords.CONTEXTUAL if w not in ("anything", "Self")],
)
def test_lex_21_contextual_word_as_name(word: str) -> None:
    sink = Sink()
    parse(HEAD + f"to main, needs console:\n    let {word} be 1\n", sink=sink)
    assert [d.code for d in sink.items] == ["SAY-W0114"]


def test_lex_21_anything_as_parameter_name() -> None:
    sink = Sink()
    parse(HEAD + "to f anything:\n    give back anything\n", sink=sink)
    assert [d.code for d in sink.items] == ["SAY-W0114"]
