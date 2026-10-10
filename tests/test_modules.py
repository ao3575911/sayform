"""Modules and the `strict` dialect (M10): MOD-01..14, DIA-01..08 (spec/10-modules-dialects.md)."""

from __future__ import annotations

from pathlib import Path

import pytest
from runner import run_source

from sayform import cli
from sayform.checker import check_module
from sayform.diagnostics import SayError, Sink
from sayform.modules import load_tree
from sayform.parser import parse

PRICES = "module shop.prices\nedition 0\n\nto price-of n:\n    give back n * 2\n\n\nlet tax be 10\n"
APP = "edition 0\n{uses}\nneeds console\n\nto main, needs console:\n{body}"


def tree(tmp_path: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        f = tmp_path / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
    return tmp_path / next(iter(files))


def app(uses: str, body: str) -> str:
    return APP.format(uses=uses, body="".join(f"    {ln}\n" for ln in body.splitlines()))


def code_of(path: Path) -> str:
    with pytest.raises(SayError) as e:
        load_tree(str(path))
    return e.value.code


def run_tree(tmp_path: Path, capsys: pytest.CaptureFixture[str], files: dict[str, str]) -> tuple[int, str]:
    code = cli.main(["run", str(tree(tmp_path, files))])
    return code, capsys.readouterr().out


def test_mod_01_header_order() -> None:
    assert run_source("needs console\nedition 0\n").code == "SAY-E0702"


def test_mod_02_path_mismatch(tmp_path: Path) -> None:
    root = tree(
        tmp_path, {"app.say": app("use shop.prices", "show 1"), "shop/prices.say": PRICES.replace("shop.", "x.")}
    )
    assert code_of(root) == "SAY-E0701"


def test_mod_03_missing_module(tmp_path: Path) -> None:
    assert code_of(tree(tmp_path, {"app.say": app("use shop.nowhere", "show 1")})) == "SAY-E0701"


def test_mod_04_cycle(tmp_path: Path) -> None:
    files = {
        "app.say": app("use alpha", "show 1"),
        "alpha.say": "module alpha\nedition 0\nuse beta\n\nlet x be 1\n",
        "beta.say": "module beta\nedition 0\nuse alpha\n\nlet y be 2\n",
    }
    with pytest.raises(SayError) as e:
        load_tree(str(tree(tmp_path, files)))
    assert e.value.code == "SAY-E0701" and "alpha -> beta -> alpha" in e.value.diag.what


def test_mod_05_use_names(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    files = {"app.say": app("use shop.prices: price-of", "show price-of(3)"), "shop/prices.say": PRICES}
    assert run_tree(tmp_path, capsys, files) == (0, "6\n")


def test_mod_06_qualified_by_last_segment(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    files = {"app.say": app("use shop.prices", "show prices.tax\nshow prices.price-of(4)"), "shop/prices.say": PRICES}
    assert run_tree(tmp_path, capsys, files) == (0, "10\n8\n")


def test_mod_07_alias(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    files = {"app.say": app("use shop.prices as sp", "show sp.tax"), "shop/prices.say": PRICES}
    assert run_tree(tmp_path, capsys, files) == (0, "10\n")


def test_mod_08_no_star_import() -> None:
    assert run_source("edition 0\nuse shop.prices: *\n").code == "SAY-E0305"


def test_mod_09_edition_missing_warns() -> None:
    sink = Sink()
    parse("module m\nneeds console\n\nto main, needs console:\n    show 1\n", sink=sink)
    assert [(d.code, d.severity) for d in sink.items] == [("SAY-E1012", "warning")]


def test_mod_10_edition_required_under_strict() -> None:
    assert run_source("module m\ndialect strict\n").code == "SAY-E1012"


def test_mod_11_exports_every_definition(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    lib = "module lib\nedition 0\n\na Box has a size (a number)\n\n\nto big of b:\n    give back b's size * 10\n"
    files = {"app.say": app("use lib: Box, big", "show big of (Box with size 2)"), "lib.say": lib}
    assert run_tree(tmp_path, capsys, files) == (0, "20\n")


def test_mod_12_use_grants_no_capabilities(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    lib = 'module noisy\nedition 0\nneeds console\n\nto shout, needs console:\n    show "!"\n'
    src = "edition 0\nuse noisy: shout\n\nto main:\n    shout()\n"
    assert cli.main(["run", str(tree(tmp_path, {"app.say": src, "noisy.say": lib}))]) == 70
    capsys.readouterr()


def test_mod_13_conflicting_definitions(tmp_path: Path) -> None:
    files = {
        "app.say": app("use shop.prices", "show 1") + "\n\nto price-of n:\n    give back n\n",
        "shop/prices.say": PRICES,
    }
    assert cli.main(["run", str(tree(tmp_path, files))]) == 2


def test_mod_14_module_search_uses_say_toml_root(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    files = {"src/app.say": app("use shop.prices", "show prices.tax"), "shop/prices.say": PRICES, "say.toml": ""}
    assert run_tree(tmp_path, capsys, files) == (0, "10\n")


# ---- DIA -----------------------------------------------------------------------------------
STRICT = "module m\nedition 0\ndialect strict\n\n"


def strict(body: str) -> str:
    try:
        check_module(parse(STRICT + body, name="m"))
    except SayError as e:
        return e.code
    return ""


def test_dia_01_strict_ascii_names() -> None:
    assert strict("let naïve be 1\n") == "SAY-E0124"


def test_dia_02_strict_typed_exports() -> None:
    assert strict("to f x:\n    give back x\n") == "SAY-E0205"
    assert strict("to f x (a number) giving a number:\n    give back x\n") == ""


VARIANT = "a Shape is one of:\n    circle with a radius (a number)\n    square with a side (a number)\n\n\n"
MATCH = "to f x (a Shape) giving a number:\n    match x:\n        when circle:\n            give back 1\n"


def test_dia_03_non_exhaustive_is_error_under_strict() -> None:
    assert strict(VARIANT + MATCH) == "SAY-W0911"


def test_dia_04_non_exhaustive_warns_without_strict() -> None:
    sink = Sink()
    check_module(parse("edition 0\n\n" + VARIANT + MATCH, name="m"), sink)
    assert [d.code for d in sink.items] == ["SAY-W0911"] and "square" in sink.items[0].what


def test_dia_05_unknown_dialect() -> None:
    assert run_source("edition 0\ndialect bogus\n").code == "SAY-E0706"


@pytest.mark.parametrize("d", ["money", "units", "ieee", "quick-script"])
def test_dia_06_v01_dialects_rejected(d: str) -> None:
    assert run_source(f"edition 0\ndialect {d}\n").code == "SAY-E1013"


def test_dia_07_strict_rejects_foreign() -> None:
    assert run_source("edition 0\nuse python numpy as np\ndialect strict\n").code == "SAY-E1013"


def test_dia_08_strict_is_lexical_per_module(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    lib = STRICT.replace("module m", "module lib") + "to f x (a number) giving a number:\n    give back x\n"
    files = {"app.say": app("use lib: f", "let naïve be f(1)\nshow naïve"), "lib.say": lib}
    assert run_tree(tmp_path, capsys, files) == (0, "1\n")
