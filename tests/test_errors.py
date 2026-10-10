"""Issue #14: the 14 remaining reachable spec error codes are emitted (spec/14-errors.md)."""

from __future__ import annotations

from pathlib import Path

import pytest
from runner import run, run_source
from test_modules import tree

from sayform import cli
from sayform.checker import check_module
from sayform.diagnostics import Sink
from sayform.parser import parse

FN = "to move item from src to dst:\n    give back dst\n"
ADD = "to add u v:\n    give back u\n"
CASES = [
    ("E0111", "let x be 1\nx = 5"),
    ("E0112", "show (yes and 1)"),
    ("E0112", "show (not 1)"),
    ("E0112", 'show (2 or "x")'),
    ("E0201", "if 1:\n    show 1"),
    ("E0201", 'while "go":\n    show 1'),
    ("E0201", 'show ("a" is less than 1)'),
    ("E0203", "show (5 seconds + 3)"),
    ("E0203", "show (2 is less than 1s)"),
    ("E0408", "show move(1, from=2, via=3)"),
    ("E0409", "show move(1, from=2)"),
    ("E0410", "show move(1, 2, 3, 4)"),
    ("E0410", "show move(1, from=2, from=3)"),
    ("E0403", "show add(1, 2)"),
    ("E0821", 'show {"a": 1, "a": 2}'),
    ("E0821", "show {1, 2, 1}"),
]


@pytest.mark.parametrize(("code", "body"), CASES, ids=[f"{c}-{i}" for i, (c, _) in enumerate(CASES)])
def test_static_codes(code: str, body: str) -> None:
    head = ADD if code == "E0403" else FN
    assert run(body, head).code == f"SAY-{code}"


def test_runtime_paths_still_e0212() -> None:
    assert run("let n be 1\nlet m be 2\nshow (n or m)").code == "SAY-E0212"
    assert run("show move(1, from=2, to=3)", FN).out == ["3"]
    assert run("show move(1, 2, 3)", FN).out == ["3"]


@pytest.mark.parametrize(
    ("code", "src"),
    [
        ("E0704", "operator plus-ish takes 2 operands\n"),
        ("E0705", "edition 0\ndialect strict, strict\n"),
        ("E1011", "edition 1\n"),
    ],
)
def test_header_codes(code: str, src: str) -> None:
    assert run_source(src).code == f"SAY-{code}"


def test_w0201_ignored_problem() -> None:
    src = "to load name, may fail with not-found:\n    give back name\n\n\nto main, may fail with not-found:\n    load(1)\n    let v be try load(2)\n"
    sink = Sink()
    check_module(parse(src, sink=sink), sink)
    assert [d.code for d in sink.items] == ["SAY-W0201"]


def test_e0404_two_modules_define_one_name(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    one = "module {m}\nedition 0\n\na Price has an amount (a number)\n"
    files = {
        "app.say": "edition 0\nuse one\nuse two\nneeds console\n\nto main, needs console:\n    show 1\n",
        "one.say": one.format(m="one"),
        "two.say": one.format(m="two"),
    }
    assert cli.main(["run", str(tree(tmp_path, files))]) == 2 and "SAY-E0404" in capsys.readouterr().err
