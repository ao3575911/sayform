"""Lexical conformance (spec/15-conformance.md section 2, spec/02-lexical.md).

Each test is named after its LEX id. Parts of a LEX test that need the parser or the
formatter (E0109/E0113/W0114 reporting, `say fmt` output) are covered in later milestones
and listed in README's status table.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from sayform.diagnostics import SayError
from sayform.keywords import CONTEXTUAL, RESERVED
from sayform.lexer import decode, lex


def kinds(src: str) -> list[tuple[str, object]]:
    return [(t.kind, t.value) for t in lex(src).tokens if t.kind not in ("NEWLINE", "EOF")]


def code_of(src: str | bytes) -> str:
    with pytest.raises(SayError) as e:
        lex(decode(src) if isinstance(src, bytes) else src)
    return e.value.code


def test_lex_01_utf8() -> None:
    assert ("NAME", "café") in kinds(decode("let café be 1\n".encode()))
    assert code_of(b"let x be \xff\n") == "SAY-E0105"


def test_lex_02_bom() -> None:
    assert kinds(decode(b"\xef\xbb\xbflet x be 1\n"))[0] == ("NAME", "let")
    assert code_of(b"let x\xef\xbb\xbf be 1\n") == "SAY-E0105"


def test_lex_03_line_ends() -> None:
    assert kinds("let x be 1\r\nlet y be 2\r\n") == kinds("let x be 1\nlet y be 2\n")
    assert code_of("let x be 1\rlet y be 2\n") == "SAY-E0105"


def test_lex_04_tab() -> None:
    assert code_of("to main:\n\tshow 1\n") == "SAY-E0101"


def test_lex_05_three_spaces() -> None:
    with pytest.raises(SayError) as e:
        lex("to main:\n   show 1\n")
    assert e.value.code == "SAY-E0102"
    assert "3 spaces" in e.value.diag.what


def test_lex_06_continuation() -> None:
    toks = kinds("let x be (1 +\n        2)\n")
    assert ("INDENT", None) not in [(k, None) for k, _ in toks]
    assert code_of("let x be 1 \\\n    + 2\n") == "SAY-E0105"


def test_lex_07_trailing_full_stop() -> None:
    assert kinds("show 5.\n") == kinds("show 5\n")


def test_lex_08_hyphen_underscore_one_name() -> None:
    assert kinds("total-cost\n") == kinds("total_cost\n")


def test_lex_09_minus_and_digit_joiner() -> None:
    assert kinds("x-1\n") == [("NAME", "x"), ("OP", "-"), ("INT", 1)]
    assert code_of("let level_2 be 1\n") == "SAY-E0105"


def test_lex_10_keyword_case() -> None:
    assert code_of("Let x be 1\n") == "SAY-E0103"
    assert ("NAME", "A") in kinds("for any A\n")


def test_lex_11_apostrophe() -> None:
    assert kinds("the user's name\n")[2] == ("POSS", "'s")
    assert ("SYM", "x") in kinds("let s be 'x\n")
    assert code_of("let x be '\n") == "SAY-E0105"


@pytest.mark.parametrize("src", ["007", "1_000", ".5", "5. + 1", "1e3"])
def test_lex_12_bad_numbers(src: str) -> None:
    assert code_of(f"let x be {src}\n") == "SAY-E0135"


def test_lex_12_approx_exponent() -> None:
    assert ("APPROX", 1000.0) in kinds("let x be approx 1e3\n")


def test_lex_13_decimal_scale() -> None:
    value = kinds("let x be 12.50\n")[-1]
    assert value[0] == "DEC"
    assert isinstance(value[1], Decimal) and value[1].as_tuple().exponent == -2


def test_lex_14_escapes() -> None:
    assert kinds('show "a\\tb\\n\\\\\\"\\u{1F600}"\n')[1] == ("TEXT", ['a\tb\n\\"\U0001f600'])
    assert code_of('show "\\q"\n') == "SAY-E0136"


def test_lex_15_unterminated() -> None:
    assert code_of('show "abc\n') == "SAY-E0106"


def test_lex_16_interpolation() -> None:
    parts = kinds('show "a {x + 1} \\{b\\}"\n')[1][1]
    assert isinstance(parts, list) and parts[0] == "a " and parts[-1] == " {b}"


def test_lex_17_triple_quote_dedent() -> None:
    src = 'let t be """\n    hi\n      there\n    """\n'
    assert kinds(src)[-1] == ("TEXT", ["hi\n  there"])


def test_lex_18_durations() -> None:
    toks = kinds("wait 5 seconds\nwait 5s\nwait 200ms\nwait 2 min\n")
    assert ("DUR", (5, "s")) in toks and ("DUR", (200, "ms")) in toks
    assert ("NAME", "seconds") in toks and ("NAME", "min") in toks


def test_lex_19_comments_kept() -> None:
    lexed = lex("# heading\nshow 1  # after\n")
    assert [c[2] for c in lexed.comments] == ["# heading", "# after"]


def test_lex_20_reserved_words_tokenise_as_words() -> None:
    assert len(RESERVED) == 63
    for w in RESERVED:
        if w != "'s":
            assert kinds(f"{w}\n")[0] == ("NAME", w)


def test_lex_21_contextual_words_are_names() -> None:
    assert len(CONTEXTUAL) == 89
    for w in CONTEXTUAL:
        assert kinds(f"{w}\n")[0][0] == "NAME"


@pytest.mark.parametrize("alias,ascii_", [("≠", "!="), ("≤", "<="), ("≥", ">="), ("≡", "≡")])
def test_lex_22_unicode_aliases(alias: str, ascii_: str) -> None:
    assert kinds(f"a {alias} b\n")[1] == ("OP", ascii_)


@pytest.mark.parametrize("src", ["let x be 1;\n", "let x be @\n", "let x be 2 ** 3\n"])
def test_lex_23_stray_characters(src: str) -> None:
    with pytest.raises(SayError) as e:
        lex(src)
    assert e.value.code == "SAY-E0105" and e.value.diag.try_


def test_lex_24_normalisation() -> None:
    assert code_of("let cafe\u0301 be 1\n") == "SAY-E0105"
    lexed = lex("let café be 1\n")
    assert lexed.non_ascii_words and lexed.non_ascii_words[0][0] == "café"
