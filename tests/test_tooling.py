"""Tooling (M9): TOOL-*, EXP-*, TEST-*, ERR-* rows (spec/13-tooling.md, spec/14-errors.md)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from hypothesis import given, settings
from roundtrip.test_laws import EXPRS, with_expr
from runner import run, run_source

from sayform import cli
from sayform.codes import ACTIVE, CODES, RETIRED
from sayform.explain import explain
from sayform.parser import parse

ROOT = Path(__file__).resolve().parents[1]
E2 = """module club.members
edition 0

a Person has a name (text) and an age (an integer, default 0)


to count-adults of people (a list of Person) giving an integer:
    give back count of (people where age is at least 18)
"""
E3 = """edition 0
needs network and tasks

to fetch-forecast for city (text) from source (text) giving a number, needs network, may fail with not-found:
    give back 1


to fastest-forecast for city (text) giving a number, needs network and tasks, may fail with several and timed-out:
    within 3 seconds:
        give back first of:
            fetch-forecast for city from "bom"
            fetch-forecast for city from "backup"
"""
TESTS = """edition 0

note: The mean.
    example: average of [1, 2, 3] gives 2
    example: average of [] fails with empty-list
to average of numbers (a list of numbers) giving a number, may fail with empty-list:
    if numbers is empty:
        give back problem empty-list
    give back (sum of numbers) / (count of numbers)


check "exact decimals":
    check that 0.1 + 0.2 equals 0.3
    check that 1 / 4 equals 0.25

check that average of [2, 4] is a number
check that (average of []) fails with empty-list
check that 2 > 1
check that quote (x + 1) matches quote (?a + 1)
"""


def say(tmp_path: Path, capsys: pytest.CaptureFixture[str], text: str, *args: str) -> tuple[int, str, str]:
    f = tmp_path / "prog.say"
    f.write_text(text, encoding="utf-8")
    code = cli.main([a.replace("FILE", str(f)) for a in args])
    out = capsys.readouterr()
    return code, out.out, out.err


HELLO = 'edition 0\nneeds console\n\nto main, needs console:\n    show "hi"\n'


# ---- TOOL ----------------------------------------------------------------------------------
def test_tool_01_run_ok(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert say(tmp_path, capsys, HELLO, "run", "FILE")[:2] == (0, "hi\n")


def test_tool_02_run_exit_codes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    prob = "edition 0\n\nto main, may fail with not-found:\n    give back problem not-found\n"
    assert say(tmp_path, capsys, prob, "run", "FILE")[0] == 1
    assert say(tmp_path, capsys, "edition 0\nshow\n", "run", "FILE")[0] == 2
    assert say(tmp_path, capsys, HELLO, "run", "FILE", "--deny", "console")[0] == 4
    assert say(tmp_path, capsys, "edition 0\n\nto main:\n    give back 1 // 0\n", "run", "FILE")[0] == 70


def test_tool_03_diagnostics_on_stderr_output_on_stdout(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, err = say(tmp_path, capsys, "edition 0\nlet x be\n", "run", "FILE")
    assert code == 2 and out == "" and "error[SAY-" in err


def test_tool_04_fmt_check(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = say(tmp_path, capsys, HELLO.replace("show", "show  "), "fmt", "--check", "FILE")
    assert code == 1 and out.startswith("---")


def test_tool_05_fmt_rewrites_and_is_idempotent(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    say(tmp_path, capsys, HELLO, "fmt", "FILE")
    assert say(tmp_path, capsys, (tmp_path / "prog.say").read_text(), "fmt", "--check", "FILE")[0] == 0


def test_tool_06_fmt_symbols(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    say(tmp_path, capsys, HELLO, "fmt", "--symbols", "FILE")
    assert 'show("hi")' in (tmp_path / "prog.say").read_text()


def test_tool_07_explain_text_and_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = say(tmp_path, capsys, HELLO, "explain", "FILE")
    assert code == 0 and "Show the text" in out or 'Show "hi"' in out
    code, out, _ = say(tmp_path, capsys, HELLO, "explain", "FILE", "--json")
    assert json.loads(out)["version"] == "say-json/1"


def test_tool_08_explain_file_line(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = say(tmp_path, capsys, E3, "explain", "FILE:9")
    assert code == 0 and "fastest-forecast" in out and "Function `fetch-forecast`" not in out


def test_tool_09_check_clean_and_errors(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert say(tmp_path, capsys, HELLO, "check", "FILE")[0] == 0
    code, _, err = say(tmp_path, capsys, "edition 0\n\nto main:\n    show 1\n", "check", "FILE")
    assert code == 2 and "SAY-E0501" in err


def test_tool_10_check_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = say(tmp_path, capsys, "edition 0\nshow zork\n", "check", "FILE", "--json")
    doc = json.loads(out)
    assert code == 2 and doc["version"] == "say-json/1" and doc["diagnostics"][0]["code"].startswith("SAY-E")


def test_tool_11_test_pass_fail_exit(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = say(tmp_path, capsys, TESTS, "test", "FILE")
    assert code == 0 and out.strip() == "8 passed, 0 failed"
    code, out, err = say(tmp_path, capsys, TESTS.replace("equals 0.25", "equals 0.5"), "test", "FILE")
    assert code == 3 and "1 failed" in out and "expected 0.5, actual 0.25" in err


def test_tool_12_test_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = say(tmp_path, capsys, TESTS, "test", "FILE", "--json")
    doc = json.loads(out)
    assert code == 0 and doc["passed"] == 8 and all(t["ok"] for t in doc["tests"])


def test_tool_13_test_compile_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert say(tmp_path, capsys, "edition 0\ncheck that\n", "test", "FILE")[0] == 2


def test_tool_14_hash_and_defs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = say(tmp_path, capsys, HELLO, "hash", "FILE", "--defs")
    lines = out.splitlines()
    assert code == 0 and re.match(r"b3:[a-z2-7]+  prog$", lines[0]) and lines[1].endswith("prog.main")


def test_tool_15_core_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = say(tmp_path, capsys, HELLO, "core", "FILE", "--json")
    assert code == 0 and json.loads(out)["version"] == "say-json/1"


def test_tool_16_version(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["--version"]) == 0 and "spec 0.1-lite" in capsys.readouterr().out


def test_tool_17_repl_echo_and_commands() -> None:
    lines = iter(["let x be 2 + 3", "show x", ":symbols", "show x", ":type x", ":caps", ":quit"])
    out: list[str] = []
    assert cli.repl(lambda prompt: next(lines), out.append) == 0
    assert out == ["let x be 2 plus 3", "show x", "5", "show(x)", "5", "an integer", "console"]


def test_tool_18_repl_definitions_and_grant() -> None:
    lines = iter(
        ["to double n:", "    give back n * 2", "", "show (double of 4)", ":grant clock", "yes", ":caps", ":quit"]
    )
    out: list[str] = []
    cli.repl(lambda prompt: next(lines), out.append)
    assert out[0] == "to double n:\n    give back n times 2" and "8" in out and out[-1] == "console, clock"


def test_tool_19_shuffle_tasks_flag(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    prog = "edition 0\nneeds console and tasks\n\nto main, needs console and tasks:\n    together:\n"
    prog += "".join(f'        show "{c}"\n' for c in "abcd")
    a = say(tmp_path, capsys, prog, "run", "FILE", "--shuffle-tasks", "7")
    b = say(tmp_path, capsys, prog, "run", "FILE", "--shuffle-tasks", "7")
    assert a == b and sorted(a[1].split()) == list("abcd")


def test_tool_20_cli_has_no_network_imports() -> None:
    text = (ROOT / "src" / "sayform" / "cli.py").read_text()
    assert not re.search(r"^\s*(import|from) (socket|urllib|http|requests)", text, re.M)


# ---- EXP -----------------------------------------------------------------------------------
def test_exp_01_rewording_is_not_a_change() -> None:
    a = explain(parse("edition 0\nlet area be r's width times r's height\nlet r be 1\n", name="m"))
    b = explain(parse("edition 0\nlet area = r.width * r.height\nlet r = 1\n", name="m"))
    assert a == b and a[2] == "L2: Let `area` be r's width times r's height, which never changes."


def test_exp_02_implicit_it_and_postfix_clause() -> None:
    got = explain(parse(E2, name="members"))
    assert got[0:2] == ["Module club.members, edition 0.", "It may use: nothing."]
    assert got[3] == "Function `count-adults`: takes people (a list of Person); gives an integer; may use nothing."
    assert got[4] == "L8:   Give back the number of items in people whose age is at least 18."


def test_exp_03_race_with_deadline() -> None:
    got = explain(parse(E3, name="race"))[4:]
    assert got == [
        "Function `fastest-forecast`: takes for city (text); gives a number; may use network and tasks;"
        " may fail with several and timed-out.",
        "L9:   Within 3 seconds, otherwise fail with timed-out:",
        "L10:     Give back the first of these to succeed, run at the same time, cancelling the rest:",
        'L11:       (a) the result of fetch-forecast given for city, from "bom".',
        'L12:       (b) the result of fetch-forecast given for city, from "backup".',
    ]


def ex_main(body: str, header: str = "", needs: str = "console") -> list[str]:
    main = "".join("    " + ln + "\n" for ln in body.splitlines())
    src = f"edition 0\nneeds {needs}\n\n{header}\n\nto main, needs {needs}:\n{main}"
    return [ln.split(": ", 1)[1].strip() for ln in explain(parse(src, name="m")) if re.match(r"L\d+:", ln)]


def test_exp_04_binding_family() -> None:
    assert ex_main("let x be 1, changeable\nset x to 2\nshow x") == [
        "Let `x` be 1, which can change later.",
        "Change `x` to 2.",
        "Show x.",
    ]


def test_exp_05_control_family() -> None:
    got = ex_main("let n be 3\nif n > 2:\n    show 1\notherwise:\n    show 2\nrepeat 2 times:\n    show n")
    assert got[1:] == ["If n is greater than 2:", "Show 1.", "Otherwise:", "Show 2.", "Repeat 2 times:", "Show n."]


def test_exp_06_loops_and_returns() -> None:
    got = ex_main("for each x in [1, 2]:\n    if x = 2:\n        stop\n    skip\nwhile no:\n    show 1")
    assert "For each `x` in [1, 2]:" in got and "Stop the loop." in got and "Skip to the next item." in got
    assert "While no:" in got


def test_exp_07_match_family() -> None:
    got = ex_main("match 3:\n    when 1:\n        show 1\n    otherwise:\n        show 2")
    assert got == ["Look at 3:", "When it is 1:", "Show 1.", "Otherwise:", "Show 2."]


def test_exp_08_concurrency_family() -> None:
    got = ex_main('together:\n    show "a"\n    show "b"', needs="console and tasks")
    assert got == ["Run these at the same time and wait for all of them:", '(a) show the text "a".', '(b) show the text "b".']


def test_exp_09_symbolic_and_lambda() -> None:
    got = ex_main("let e be quote (x + 1)\nlet f be given n, n * 2\nshow f(2)")
    assert got[0] == "Let `e` be the expression `x + 1`, which never changes."
    assert got[1] == "Let `f` be a function that, given n, gives n times 2, which never changes."


def test_exp_10_records_and_checks() -> None:
    src = "edition 0\n\na Box has a size (a number), where size is at least 0\n\n\ncheck that 1 + 1 equals 2\n"
    got = explain(parse(src, name="m"))
    assert got[2] == "Record `Box`: has a size (a number); every Box must satisfy: size is at least 0."
    assert got[3] == "L6: Check that 1 plus 1 equals 2."


def test_exp_11_footnotes_beyond_depth_3() -> None:
    src = "edition 0\nneeds console\n\nto main, needs console:\n    show (1 + 2 + 3 + 4 + 5 + 6)\n"
    got = explain(parse(src, name="m"))
    assert got[3] == "L5:   Show (1) plus 4 plus 5 plus 6."
    assert got[4:] == ["    where (1) is 1 plus 2 plus 3."]


@settings(max_examples=60, deadline=None)
@given(EXPRS)
def test_exp_12_totality_on_rt_generator(e: object) -> None:
    lines = explain(with_expr(e))
    assert lines and all(isinstance(x, str) and x for x in lines)


# ---- TEST ----------------------------------------------------------------------------------
def checks(src: str) -> list[bool]:
    from sayform.evaluator import run_checks

    return [r.ok for r in run_checks(parse(src + cli.note_examples(src), name="t"))]


def test_test_01_to_05_line_forms() -> None:
    src = "edition 0\n\ncheck that 1 equals 1\ncheck that yes\ncheck that 1 is a number\n"
    src += "check that problem nope fails with nope\ncheck that quote (y) matches quote (?a)\n"
    assert checks(src) == [True] * 5


def test_test_06_block_form() -> None:
    assert checks(
        'edition 0\n\ncheck "b":\n    let x be 2\n    check that x equals 2\n    check that x equals 3\n'
    ) == [
        True,
        False,
    ]


def test_test_07_note_examples_run() -> None:
    assert checks(TESTS) == [True] * 8


def test_test_08_e1004_check_in_function() -> None:
    assert run("check that 1 equals 1").code == "SAY-E1004"


def test_test_09_e1005_malformed_example() -> None:
    with pytest.raises(Exception, match="E1005"):
        cli.note_examples("note: x\n    example: average of [1] is 1\n")


def test_test_10_failure_output_has_expected_actual_explain(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _, _, err = say(tmp_path, capsys, "edition 0\n\ncheck that 2 + 2 equals 5\n", "test", "FILE")
    assert "expected 5, actual 4" in err and "why: Check that 2 plus 2 equals 5." in err


# ---- ERR -----------------------------------------------------------------------------------
ERR_BODIES = {
    "E0131": ("if yes:\nshow 1", ""),
    "E0181": ("show [1, 2][0]", ""),
    "E0301": ("let x be 1\nlet x be 2\nshow x", ""),
    "E0302": ("let x be 1\nset x to 2\nshow x", ""),
    "E0304": ("show zork", ""),
    "E0904": ("match 1:\n    when 1 or ?x:\n        show 1\n    otherwise:\n        show 2", ""),
    "E0905": ("let [?a, ?b] be [1, 2]\nshow 1", ""),
    "E1004": ("check that 1 equals 1", ""),
}


@pytest.mark.parametrize("code", sorted(ERR_BODIES))
def test_err_codes(code: str) -> None:
    body, header = ERR_BODIES[code]
    assert run(body, header).code == f"SAY-{code}"


@pytest.mark.parametrize(
    ("code", "src"),
    [("E0702", "needs console\nedition 0\n"), ("E0706", "edition 0\ndialect bogus\n")],
)
def test_err_header_codes(code: str, src: str) -> None:
    assert run_source(src).code == f"SAY-{code}"


def test_err_format_five_parts_text_and_json() -> None:
    from sayform.diagnostics import SayError

    for code in sorted(ACTIVE)[:10]:
        d = SayError(code.removeprefix("SAY-"), 3).diag
        text, doc = d.render(), d.to_json()
        assert all(k in text for k in ("-->", " what: ", "  why: ", "  try: ")) and code in text
        assert {"code", "what", "why", "try"} <= set(doc)


def test_err_retired_never_emitted() -> None:
    src = "".join(p.read_text() for p in (ROOT / "src" / "sayform").glob("*.py") if p.name != "codes.py")
    for code in [*RETIRED, "SAY-E0119"]:
        assert f'"{code.removeprefix("SAY-")}"' not in src
    assert not [c for c in CODES if c.startswith("SAY-E00")] or all(c in RETIRED for c in CODES if "E00" in c)
