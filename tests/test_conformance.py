"""Golden programs G-01…G-14 (spec/15-conformance.md section 15), byte-exact. Every directory
under conformance/golden with an expect.toml is discovered; programs run on the virtual clock."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest
from runner import run_source

from sayform import cli
from sayform.explain import explain
from sayform.lexer import lex
from sayform.parser import parse
from sayform.printer import print_module
from sayform.scs import hash_module, show_hash, to_json

GOLDEN = Path(__file__).resolve().parents[1] / "conformance" / "golden"
DIRS = sorted(p.parent for p in GOLDEN.glob("*/expect.toml"))


def expect(d: Path) -> dict[str, object]:
    return dict(tomllib.loads((d / "expect.toml").read_text())["expect"])


def source(d: Path) -> str:
    return (d / "program.say").read_text(encoding="utf-8")


def test_all_fourteen_goldens_present() -> None:
    assert [d.name for d in DIRS] == [f"G-{i:02}" for i in range(1, 15)]


@pytest.mark.parametrize("d", DIRS, ids=lambda d: d.name)
def test_output(d: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    exp = expect(d)
    monkeypatch.chdir(d)
    want = (d / str(exp["stdout"])).read_text(encoding="utf-8")
    if exp["mode"] == "test":
        assert cli.main(["test", "program.say"]) == exp["exit"]
        assert capsys.readouterr().out == want
        return
    r = run_source(source(d))
    assert r.exit == exp["exit"] and "".join(x + "\n" for x in r.out) == want
    assert ([r.code] if r.code else []) == exp.get("diagnostics", [])


@pytest.mark.parametrize("d", DIRS, ids=lambda d: d.name)
def test_surfaces_explain_hash_core(d: Path) -> None:
    exp, text = expect(d), source(d)
    name = text.split("\n", 1)[0].removeprefix("module ")
    mod = parse(text, name=name)
    comments = list(lex(text).comments)
    assert print_module(mod, "words", comments) == (d / str(exp["words"])).read_text(encoding="utf-8")
    assert print_module(mod, "symbols", comments) == (d / str(exp["symbols"])).read_text(encoding="utf-8")
    assert "\n".join(explain(mod)) + "\n" == (d / str(exp["explain"])).read_text(encoding="utf-8")
    assert show_hash(hash_module(mod)[1]) == exp["hash"]
    assert json.loads((d / "core.json").read_text())["core"] == json.loads(json.dumps(to_json(mod)))


def test_g01_explain_is_normative() -> None:
    assert (GOLDEN / "G-01" / "explain.txt").read_text().splitlines()[-1] == 'L7:   Show the text "Hello, world".'
    assert (GOLDEN / "G-02" / "stdout.txt").read_text() == "GST: 1.6690\nRounded: 1.67\n"
    assert (GOLDEN / "G-08" / "stdout.txt").read_text() == "x * y\nyes\n"
