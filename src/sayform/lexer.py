"""Lexer for edition 0 (spec/02-lexical.md).

Produces tokens with NEWLINE / INDENT / DEDENT (the Python algorithm, spec 02 section 2.7),
words in canonical `-` spelling (D3), exact number literals, text with interpolation parts,
symbol literals, pattern variables, possessive `'s`, and note blocks. Comments are kept as
trivia in `Lexed.comments`.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from .diagnostics import SayError
from .keywords import RESERVED_SET, TIME_UNITS

OPS = (
    "===", "..<", "...", "==", "=>", "!=", "<=", ">=", ":=", "+=", "++", "->", "//",
    "??", "?.", "?[", "~=", "|>", "||", "&&", "..",
    "=", "<", ">", "+", "-", "*", "/", "%", "^", "?", "~", "|", "!", ".", ",", ":",
    "(", ")", "[", "]", "{", "}", "`",
)  # fmt: skip
ALIASES = {"\u2260": "!=", "\u2264": "<=", "\u2265": ">=", "\u2261": "\u2261", "\u2208": "in"}
OPENERS = {"(": ")", "[": "]", "{": "}"}


@dataclass
class Tok:
    kind: str  # NAME INT DEC APPROX TEXT SYM PATVAR POSS DUR OP NEWLINE INDENT DEDENT NOTE EOF
    value: Any
    line: int
    col: int
    spaced: bool = True  # whitespace (or line start) before the token
    raw: str = ""

    def is_op(self, *ops: str) -> bool:
        return self.kind == "OP" and self.value in ops

    def is_word(self, *words: str) -> bool:
        return self.kind == "NAME" and self.value in words

    def __repr__(self) -> str:
        return f"{self.kind}({self.value!r})@{self.line}:{self.col}"


@dataclass
class Lexed:
    tokens: list[Tok]
    comments: list[tuple[int, int, str, bool]] = field(default_factory=list)  # line,col,text,own
    source: str = ""
    non_ascii_words: list[tuple[str, int]] = field(default_factory=list)


def is_start(c: str) -> bool:
    return c != "_" and c.isidentifier()


def is_cont(c: str) -> bool:
    return c != "_" and ("a" + c).isidentifier()


def decode(data: bytes) -> str:
    """UTF-8 decode with the spec's BOM and line-end rules (spec 02 section 1)."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as e:
        line = data[: e.start].count(b"\n") + 1
        raise SayError(
            "E0105",
            line,
            1,
            text="(bytes)",
            reason="the file is not valid UTF-8",
            fix="save the file as UTF-8",
        ) from None
    if text.startswith("\ufeff"):
        text = text[1:]
    return normalise_newlines(text)


def normalise_newlines(text: str) -> str:
    if "\ufeff" in text:
        line = text[: text.index("\ufeff")].count("\n") + 1
        raise SayError(
            "E0105",
            line,
            1,
            text="U+FEFF",
            reason="a byte order mark may only appear at the start of the file",
            fix="remove the character",
        )
    text = text.replace("\r\n", "\n")
    if "\r" in text:
        line = text[: text.index("\r")].count("\n") + 1
        raise SayError(
            "E0105",
            line,
            1,
            text="U+000D",
            reason="a lone carriage return is not a line end",
            fix="use LF or CR LF line ends",
        )
    return text


class Lexer:
    def __init__(self, text: str, line: int = 1, col: int = 1, in_brackets: bool = False) -> None:
        self.s = text
        self.i = 0
        self.line = line
        self.col0 = col  # column of offset 0 on the first line
        self.line_start = 0
        self.toks: list[Tok] = []
        self.comments: list[tuple[int, int, str, bool]] = []
        self.depth = 1 if in_brackets else 0
        self.indents = [0]
        self.non_ascii: list[tuple[str, int]] = []
        self.inline = in_brackets
        self.pending_layout = False

    # -- helpers ---------------------------------------------------------------------
    def col(self, i: int | None = None) -> int:
        i = self.i if i is None else i
        base = self.col0 if self.line_start == 0 else 1
        return i - self.line_start + base

    def err(self, code: str, **kw: Any) -> SayError:
        return SayError(code, self.line, self.col(), **kw)

    def add(self, kind: str, value: Any, start: int, spaced: bool, raw: str = "") -> None:
        self.toks.append(Tok(kind, value, self.line, self.col(start), spaced, raw))

    def peek(self, k: int = 0) -> str:
        j = self.i + k
        return self.s[j] if j < len(self.s) else ""

    # -- main loop ----------------------------------------------------------------------
    def run(self) -> Lexed:
        at_line_start = not self.inline
        while True:
            if at_line_start:
                at_line_start = False
                if self.layout():
                    break
                if self.pending_layout:
                    self.pending_layout = False
                    at_line_start = True
                continue
            if self.i >= len(self.s):
                break
            c = self.s[self.i]
            if c == "\n":
                self.newline_char()
                if self.depth == 0:
                    self.end_logical_line()
                    at_line_start = True
                continue
            if c == " ":
                self.i += 1
                continue
            if c == "\t":
                if self.depth > 0:
                    self.i += 1
                    continue
                raise self.err("E0130", token="tab", expected="a space between tokens", hint="use spaces")
            if c == "#":
                self.comment()
                continue
            self.token()
        if self.depth > 0 and not self.inline:
            raise SayError(
                "E0130",
                self.line,
                self.col(),
                token="end of file",
                expected="a closing bracket",
                hint="close every `(`, `[` and `{`",
            )
        if not self.inline:
            self.end_logical_line()
            while len(self.indents) > 1:
                self.indents.pop()
                self.add("DEDENT", None, self.i, True)
        self.add("EOF", None, self.i, True)
        return Lexed(self.toks, self.comments, self.s, self.non_ascii)

    def newline_char(self) -> None:
        self.i += 1
        self.line += 1
        self.line_start = self.i

    def end_logical_line(self) -> None:
        # trailing sentence `.` (spec 02 section 2.6)
        if (
            self.toks
            and self.toks[-1].is_op(".")
            and len(self.toks) >= 2
            and self.toks[-2].kind not in ("NEWLINE", "INDENT", "DEDENT")
        ):
            self.toks.pop()
        if self.toks and self.toks[-1].kind not in ("NEWLINE", "INDENT", "DEDENT"):
            self.toks.append(Tok("NEWLINE", None, self.toks[-1].line, self.toks[-1].col + 1))

    def layout(self) -> bool:
        """Handle indentation at the start of a physical line. Returns True at EOF."""
        while True:
            start = self.i
            n = 0
            while self.peek() == " ":
                self.i += 1
                n += 1
            c = self.peek()
            if c == "":
                return True
            if c == "\t":
                raise SayError("E0101", self.line, self.col(), at_line=self.line)
            if c == "\n":
                self.newline_char()
                continue
            if c == "#":
                self.comment(own=True)
                if self.peek() == "\n":
                    self.newline_char()
                continue
            if n % 4:
                raise SayError(
                    "E0102",
                    self.line,
                    1,
                    at_line=self.line,
                    n=n,
                    suggested=(n // 4) * 4 if n % 4 < 2 else (n // 4 + 1) * 4,
                )
            if n > self.indents[-1]:
                prev = self.toks[-2] if len(self.toks) >= 2 else None
                if n != self.indents[-1] + 4 or not (prev is not None and prev.is_op(":")):
                    raise SayError(
                        "E0131",
                        self.line,
                        1,
                        what=f"Line {self.line} is indented more than the line before, but no block was opened.",
                        opener="the line above",
                    )
                self.indents.append(n)
                self.add("INDENT", None, start, True)
            else:
                if (
                    self.toks
                    and self.toks[-1].kind == "NEWLINE"
                    and len(self.toks) >= 2
                    and self.toks[-2].is_op(":")
                    and not self.toks[-2].value == "note"
                ):
                    raise SayError(
                        "E0131",
                        self.line,
                        1,
                        what=f"Line {self.line} should be indented to open the block.",
                        opener="the line above",
                    )
                while n < self.indents[-1]:
                    self.indents.pop()
                    self.add("DEDENT", None, start, True)
                if n != self.indents[-1]:
                    raise SayError(
                        "E0131",
                        self.line,
                        1,
                        what=f"Line {self.line} does not line up with any open block.",
                        opener="the block",
                    )
            if self.s.startswith("note:", self.i) and not is_cont(self.peek(5) or " "):
                self.note(n)
                return False
            return False

    def note(self, indent: int) -> None:
        line, col = self.line, self.col()
        self.i += 5
        end = self.s.find("\n", self.i)
        end = len(self.s) if end < 0 else end
        parts = [self.s[self.i : end].strip()]
        lines = [(self.line, parts[0])]
        self.i = end
        while self.i < len(self.s):
            nxt = self.s.find("\n", self.i + 1)
            nxt = len(self.s) if nxt < 0 else nxt
            body = self.s[self.i + 1 : nxt]
            stripped = body.lstrip(" ")
            if stripped and len(body) - len(stripped) > indent:
                self.newline_char()
                rel = len(body) - len(stripped) - indent - 4
                lines.append((self.line, " " * max(rel, 0) + stripped.rstrip()))
                self.i = nxt
            else:
                break
        self.toks.append(Tok("NOTE", lines, line, col, True))
        self.toks.append(Tok("NEWLINE", None, line, col))
        if self.i < len(self.s):
            self.newline_char()
        self.layout_after_note()

    def layout_after_note(self) -> None:
        self.pending_layout = True

    def comment(self, own: bool = False) -> None:
        start = self.i
        end = self.s.find("\n", self.i)
        end = len(self.s) if end < 0 else end
        text = self.s[start:end]
        own = own or not self.toks or self.toks[-1].kind in ("NEWLINE", "INDENT", "DEDENT")
        self.comments.append((self.line, self.col(start), text, own))
        self.i = end

    # -- tokens --------------------------------------------------------------------------
    def token(self) -> None:
        s, i = self.s, self.i
        c = s[i]
        prev = s[i - 1] if i > 0 else "\n"
        spaced = prev in " \n\t" or i == self.line_start
        if c == '"':
            self.text(spaced)
            return
        if c.isdigit():
            self.number(spaced)
            return
        if c == "'":
            self.apostrophe(spaced, prev)
            return
        if c == "?" and is_start(self.peek(1)):
            self.i += 1
            w = self.word_text()
            self.add("PATVAR", w, i, spaced)
            return
        if c == "_" and not is_cont(self.peek(1)) and self.peek(1) not in "-_":
            self.i += 1
            self.add("OP", "_", i, spaced)
            return
        if is_start(c):
            w = self.word_text()
            self.after_word(w, i, spaced)
            return
        if c in ALIASES:
            self.i += 1
            v = ALIASES[c]
            self.add("NAME" if v == "in" else "OP", v, i, spaced, raw=c)
            return
        if s.startswith("**", i):
            raise self.err("E0105", text="**", reason="`**` is not an operator", fix="use `^` for powers")
        if (
            c == "."
            and i + 1 < len(s)
            and s[i + 1].isdigit()
            and (spaced or (self.toks and self.toks[-1].kind == "OP" and not self.toks[-1].is_op(")", "]", "}")))
        ):
            k = i + 1
            while k < len(s) and s[k].isdigit():
                k += 1
            raise self.err("E0135", text=s[i:k], suggested="0" + s[i:k])
        for op in OPS:
            if s.startswith(op, i):
                self.i += len(op)
                if op in OPENERS:
                    self.depth += 1
                elif op in (")", "]", "}"):
                    self.depth = max(0, self.depth - 1)
                self.add("OP", op, i, spaced)
                return
        if c == "\\":
            raise self.err(
                "E0105",
                text="\\",
                reason="backslash continuation is not part of Sayform",
                fix="wrap the expression in brackets to continue it on the next line",
            )
        name = unicodedata.name(c, f"U+{ord(c):04X}")
        hint = {
            ";": "end the statement with a line end instead",
            "@": "`@` has no meaning in edition 0",
        }
        raise self.err(
            "E0105",
            text=c,
            reason=f"{name} has no meaning in Sayform source",
            fix=hint.get(c, "remove the character or put it inside text"),
        )

    def word_text(self) -> str:
        s = self.s
        start = self.i
        self.i += 1
        while self.i < len(s):
            c = s[self.i]
            if is_cont(c):
                self.i += 1
            elif c in "-_":
                nxt = self.peek(1)
                if is_start(nxt):
                    self.i += 1
                    continue
                if c == "_":
                    w = s[start : self.i]
                    raise self.err(
                        "E0105",
                        text=s[start : self.i + 2].strip(),
                        reason="a joiner must be followed by a letter",
                        fix=f"write `{w}{nxt}`" if nxt.isdigit() else f"write `{w}`",
                    )
                break
            else:
                break
        raw = s[start : self.i]
        w = raw.replace("_", "-")
        if not unicodedata.is_normalized("NFC", raw):
            raise SayError(
                "E0105",
                self.line,
                self.col(start),
                text=raw,
                reason="the name is not in Unicode Normalization Form C",
                fix=f"write `{unicodedata.normalize('NFC', raw)}`",
            )
        if not raw.isascii():
            self.non_ascii.append((w, self.line))
        if (
            len(w) >= 2 and w != w.lower() and w.casefold() in RESERVED_SET and w not in ("Set", "Nothing")
        ):  # spec-gap #3
            raise SayError("E0103", self.line, self.col(start), word=raw, kw=w.casefold())
        return w

    def after_word(self, w: str, start: int, spaced: bool) -> None:
        if w == "approx":
            j = self.i
            while j < len(self.s) and self.s[j] == " ":
                j += 1
            if j > self.i and j < len(self.s) and self.s[j].isdigit():
                self.i = j
                self.number(spaced, approx=True, start=start)
                return
        self.add("NAME", w, start, spaced, raw=self.s[start : self.i])

    def apostrophe(self, spaced: bool, prev: str) -> None:
        i = self.i
        nxt = self.peek(1)
        if (is_cont(prev) or prev in ")]") and nxt == "s" and not is_cont(self.peek(2) or " "):
            self.i += 2
            self.add("POSS", "'s", i, False)
            return
        if (spaced or prev in "([{,") and is_start(nxt):
            self.i += 1
            w = self.word_text()
            self.add("SYM", w, i, spaced)
            return
        raise self.err(
            "E0105",
            text="'",
            reason="a stray apostrophe is neither `'s` nor a symbol `'x`",
            fix="write `the f of people` for plurals, or `'name` for a symbol",
        )

    def number(self, spaced: bool, approx: bool = False, start: int | None = None) -> None:
        s = self.s
        st = self.i if start is None else start
        j = self.i
        while j < len(s) and s[j].isdigit():
            j += 1
        intpart = s[self.i : j]
        frac = ""
        if j < len(s) and s[j] == "." and j + 1 < len(s) and s[j + 1].isdigit():
            k = j + 1
            while k < len(s) and s[k].isdigit():
                k += 1
            frac = s[j + 1 : k]
            j = k
        elif j < len(s) and s[j] == "." and not (j + 1 < len(s) and s[j + 1] in ".<"):
            rest = s[j + 1 : s.find("\n", j) if s.find("\n", j) >= 0 else len(s)]
            if rest.split("#")[0].strip():
                raise self.err("E0135", text=intpart + ".", suggested=intpart)
        exp = ""
        if j < len(s) and s[j] in "eE" and (approx or (j + 1 < len(s) and (s[j + 1].isdigit() or s[j + 1] in "+-"))):
            k = j + 1
            if k < len(s) and s[k] in "+-":
                k += 1
            if k < len(s) and s[k].isdigit():
                while k < len(s) and s[k].isdigit():
                    k += 1
                exp = s[j:k]
                if not approx:
                    raise self.err(
                        "E0135",
                        text=intpart + ("." + frac if frac else "") + exp,
                        suggested=f"approx {intpart}{'.' + frac if frac else ''}{exp}",
                    )
                j = k
        text = s[self.i : j]
        if len(intpart) > 1 and intpart[0] == "0":
            raise self.err("E0135", text=text, suggested=intpart.lstrip("0") or "0")
        if j < len(s) and s[j] == "_" and j + 1 < len(s) and s[j + 1].isdigit():
            k = j
            while k < len(s) and (s[k].isdigit() or s[k] == "_"):
                k += 1
            raise self.err("E0135", text=s[self.i : k], suggested=s[self.i : k].replace("_", ""))
        self.i = j
        if approx:
            self.add("APPROX", float(text), st, spaced, raw="approx " + text)
            return
        if j < len(s) and (is_start(s[j]) or s[j] == "_"):
            k = j
            while k < len(s) and is_cont(s[k]):
                k += 1
            suffix = s[j:k]
            if suffix in ("ms", "s", "min"):
                self.i = k
                self.add("DUR", (self.numval(intpart, frac), TIME_UNITS[suffix]), st, spaced, raw=s[st:k])
                return
            raise self.err("E0135", text=s[st:k], suggested=text)
        m = re.match(r" +(milliseconds?|seconds?|minutes?)(?![\w-])", s[j:])
        if m:
            self.i = j + m.end()
            self.add("DUR", (self.numval(intpart, frac), TIME_UNITS[m.group(1)]), st, spaced, raw=s[st : self.i])
            return
        self.add("DEC" if frac else "INT", self.numval(intpart, frac), st, spaced, raw=text)

    @staticmethod
    def numval(intpart: str, frac: str) -> int | Decimal:
        return Decimal(intpart + "." + frac) if frac else int(intpart)

    def text(self, spaced: bool) -> None:
        s = self.s
        start = self.i
        line0, col0 = self.line, self.col()
        triple = s.startswith('"""', self.i)
        self.i += 3 if triple else 1
        if triple and self.peek() == "\n":
            self.newline_char()
        parts: list[Any] = []
        buf: list[str] = []
        while True:
            if self.i >= len(s):
                raise SayError("E0106", line0, col0, at_line=line0, col=col0)
            c = s[self.i]
            if triple and s.startswith('"""', self.i):
                self.i += 3
                break
            if not triple and c == '"':
                self.i += 1
                break
            if c == "\n":
                if not triple:
                    raise SayError("E0106", line0, col0, at_line=line0, col=col0)
                buf.append("\n")
                self.newline_char()
                continue
            if c == "\\":
                buf.append(self.escape())
                continue
            if c == "{":
                if buf:
                    parts.append("".join(buf))
                    buf = []
                parts.append(self.interp())
                continue
            if c == "}":
                raise self.err("E0136", c="}", what="A lone `}` inside text must be escaped.")
            buf.append(c)
            self.i += 1
        if buf:
            parts.append("".join(buf))
        if triple:
            parts = dedent_parts(parts, s, start)
        self.add("TEXT", parts, start, spaced, raw=s[start : self.i])
        self.toks[-1].line, self.toks[-1].col = line0, col0

    def escape(self) -> str:
        s = self.s
        nxt = self.peek(1)
        simple = {"\\": "\\", '"': '"', "{": "{", "}": "}", "n": "\n", "t": "\t"}
        if nxt in simple:
            self.i += 2
            return simple[nxt]
        if nxt == "u" and self.peek(2) == "{":
            end = s.find("}", self.i + 3)
            hexs = s[self.i + 3 : end] if end > 0 else ""
            if 1 <= len(hexs) <= 6 and all(h in "0123456789abcdefABCDEF" for h in hexs):
                v = int(hexs, 16)
                if v <= 0x10FFFF and not (0xD800 <= v <= 0xDFFF):
                    self.i = end + 1
                    return chr(v)
            raise self.err(
                "E0136",
                c="u" + s[self.i + 2 : end + 1] if end > 0 else "u",
                what="`\\u{…}` must name a Unicode scalar value with 1 to 6 hex digits.",
            )
        raise self.err("E0136", c=nxt)

    def interp(self) -> tuple[str, int, int]:
        s = self.s
        self.i += 1
        start, line, col = self.i, self.line, self.col()
        depth = 0
        while self.i < len(s):
            c = s[self.i]
            if c == '"':
                self.i = skip_text(s, self.i + 1)
                if self.i < 0:
                    raise SayError("E0106", line, col, at_line=line, col=col)
                continue
            if c == "\n":
                raise SayError("E0106", line, col, at_line=line, col=col)
            if c == "{":
                depth += 1
            elif c == "}":
                if depth == 0:
                    src = s[start : self.i]
                    self.i += 1
                    return (src, line, col)
                depth -= 1
            self.i += 1
        raise SayError("E0106", line, col, at_line=line, col=col)


def skip_text(s: str, j: int) -> int:
    """Index just after the text literal whose body starts at `j` (nested interpolations
    may contain text literals); -1 if it does not end on this line."""
    while j < len(s) and s[j] not in '"\n':
        if s[j] == "\\":
            j += 2
        elif s[j] == "{":
            depth, j = 0, j + 1
            while j < len(s) and s[j] != "\n" and not (s[j] == "}" and depth == 0):
                if s[j] == '"':
                    j = skip_text(s, j + 1)
                    if j < 0:
                        return -1
                    continue
                depth += {"{": 1, "}": -1}.get(s[j], 0)
                j += 1
            j += 1
        else:
            j += 1
    return j + 1 if j < len(s) and s[j] == '"' else -1


def dedent_parts(parts: list[Any], s: str, start: int) -> list[Any]:
    """Remove the closing-quote line's indentation from every line of a `\"\"\"` text."""
    flat = "".join(p if isinstance(p, str) else "\x00" for p in parts)
    last_nl = flat.rfind("\n")
    tail = flat[last_nl + 1 :] if last_nl >= 0 else ""
    if tail.strip(" ") == "" and last_nl >= 0:
        ind = len(tail)
    else:
        ind = 0
    out: list[Any] = []
    for p in parts:
        if not isinstance(p, str):
            out.append(p)
            continue
        out.append(p)
    # strip indentation at the start of each line in string parts
    res: list[Any] = []
    at_line_start = True
    for p in out:
        if not isinstance(p, str):
            res.append(p)
            at_line_start = False
            continue
        lines = p.split("\n")
        new = []
        for k, ln in enumerate(lines):
            if (k > 0 or at_line_start) and ind:
                cut = 0
                while cut < ind and cut < len(ln) and ln[cut] == " ":
                    cut += 1
                ln = ln[cut:]
            new.append(ln)
        at_line_start = p.endswith("\n")
        res.append("\n".join(new))
    if ind or (res and isinstance(res[-1], str)):
        if res and isinstance(res[-1], str):
            last = res[-1]
            if last.endswith("\n") or (last_nl >= 0 and tail.strip(" ") == ""):
                k = last.rfind("\n")
                if k >= 0 and last[k + 1 :].strip(" ") == "":
                    res[-1] = last[:k]
    return [p for p in res if p != ""]


def lex(text: str) -> Lexed:
    """Lex a whole module (text already decoded)."""
    return Lexer(normalise_newlines(text)).run()


def lex_inline(text: str, line: int, col: int) -> Lexed:
    """Lex an interpolation or note-example fragment as if inside brackets."""
    return Lexer(text, line, col, in_brackets=True).run()
