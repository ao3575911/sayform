"""Effects and capabilities (M5): CAP-01..CAP-12, CAP-16, CAP-17, CAP-20 (spec/09-effects-capabilities.md).
CAP-13..15 (tests), CAP-18 (tasks) and CAP-19 (REPL) land with M8/M9."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from runner import Result, run_source

from sayform.cli import main as say
from sayform.diagnostics import EXIT, SayError
from sayform.evaluator import program
from sayform.parser import parse


def src(body: str, needs: str = "console", header: str = "", main_needs: str | None = None) -> str:
    mn = needs if main_needs is None else main_needs
    lines = "".join("    " + ln + "\n" for ln in body.splitlines())
    head = f"needs {needs}\n" if needs else ""
    return f"edition 0\n{head}\n{header}\n\nto main{', needs ' + mn if mn else ''}:\n{lines}"


def test_cap_01_hello() -> None:
    assert run_source(src('show "hi"')).out == ["hi"]


def test_cap_02_show_without_needs() -> None:
    assert run_source(src('show "hi"', needs="")).code == "SAY-E0501"


def test_cap_03_transitive_effect() -> None:
    header = 'to greet:\n    show "hi"\n'
    assert run_source(src("greet()", header=header)).code == "SAY-E0501"
    header = 'to greet, needs console:\n    show "hi"\n'
    assert run_source(src("greet()", header=header, main_needs="")).code == "SAY-E0501"


def test_cap_04_header_covers_definitions() -> None:
    text = 'edition 0\nneeds clock\n\nto main, needs console:\n    show "x"\n'
    assert run_source(text).code == "SAY-E0501"


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "a.txt").write_text("one\ntwo\nthree", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("s", encoding="utf-8")
    old = os.getcwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(old)


def test_cap_05_files_limited_to(data_dir: Path) -> None:
    body = 'with files limited to "./data":\n    show count of split(try files.read-text("./data/a.txt"), by="\\n")'
    header = ""
    text = src(body.replace("try ", "") + "\n", needs="console and files")
    assert run_source(text).out == ["3"]
    bad = src('with files limited to "./data":\n    show files.read-text("./secret.txt")', needs="console and files")
    r = run_source(bad)
    assert (r.code, r.exit) == ("SAY-E0502", 70)
    assert header == ""


def test_cap_06_read_only(data_dir: Path) -> None:
    body = 'with files limited to "./data", read only:\n    files.write-text("x", to="./data/b.txt")'
    r = run_source(src(body, needs="console and files"))
    assert (r.code, r.exit) == ("SAY-E0502", 70)
    assert not (data_dir / "data" / "b.txt").exists()


def test_cap_07_widening(data_dir: Path) -> None:
    body = 'with files limited to "./data":\n    with files limited to "./":\n        show 1'
    assert run_source(src(body, needs="console and files")).code == "SAY-E0504"
    assert run_source(src('with console limited to "x":\n    show 1')).code == "SAY-E0504"


def test_cap_08_escaped_closure_revoked(data_dir: Path) -> None:
    body = (
        "let f be nothing, changeable\n"
        'with files limited to "./data":\n    set f to given p, files.read-text(p)\n'
        'show f("./data/a.txt")'
    )
    r = run_source(src(body, needs="console and files"))
    assert (r.code, r.exit) == ("SAY-E0502", 70)


def test_cap_09_deny_console(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    f = tmp_path / "p.say"
    f.write_text(src('show "hi"'), encoding="utf-8")
    assert say(["run", str(f), "--deny", "console"]) == 4
    assert "SAY-E0506" in capsys.readouterr().err


def test_cap_10_network_refused() -> None:
    r = run_source(src('show "hi"', needs="console and network"))
    assert (r.code, r.exit) == ("SAY-E0506", 4)


def test_cap_11_use_grants_nothing() -> None:
    text = "edition 0\n\nto main:\n    show 1\n"
    assert run_source(text).code == "SAY-E0501"


def test_cap_12_top_level_let_with_effect() -> None:
    text = 'edition 0\nneeds console\n\nlet x be show "boom"\n\nto main, needs console:\n    show 1\n'
    assert run_source(text).code == "SAY-E0501"


def test_cap_16_seeded_random() -> None:
    text = src("show random.random-integer(from=1, to=1000000)", needs="console and random")
    outs: list[list[str]] = []
    for _ in range(2):
        outs.append([])
        program(parse(text), lambda t, end="\n", sink=outs[-1]: sink.append(t), seed=7)
    assert outs[0] == outs[1] and len(outs[0]) == 1


def test_cap_17_function_value_checked_at_run_time() -> None:
    header = 'to loud, needs console:\n    show "!"\n\nto call-it f:\n    give back f()\n'
    r = run_source(src("call-it(loud)", header=header))
    assert (r.code, r.exit) == ("SAY-E0502", 70)


class Revoked:
    def check(self, effect: str, narrowing: tuple[object, ...], use: dict[str, object]) -> str:
        return "revoked"


def test_cap_20_backing_revoked_gives_problem() -> None:
    text = src('let r be show "hi"\nshow (r is a problem)', needs="console")
    got: list[str] = []
    _, value = program(parse(text), lambda t, end="\n": got.append(t), backing=Revoked())
    assert got == [] and value is None


def test_cap_clock_virtual() -> None:
    text = src("show clock.now()", needs="console and clock")
    got: list[str] = []
    program(parse(text), lambda t, end="\n": got.append(t), seed=1)
    assert got == ["0.000000"]


def test_exit_codes_table() -> None:
    assert EXIT == {"error": 2, "panic": 70, "refused": 4, "warning": 0}
    assert isinstance(Result([], 0), Result) and SayError
