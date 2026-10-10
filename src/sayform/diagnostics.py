"""Five-part diagnostics (spec/14-errors.md section 1, Law 6).

Every diagnostic has a location, a plain-English *what*, a *why*, one *try this* and a
stable code. `SayError` is raised for compile errors, panics and host refusals; warnings
are collected in a `Sink`.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from .codes import CODES

_PH = re.compile(r"\{([a-z0-9_/ ]+)(?::[^{}]*)?\}")
EXIT = {"error": 2, "panic": 70, "refused": 4, "warning": 0}


def _fill(template: str, params: dict[str, Any]) -> str:
    def sub(m: re.Match[str]) -> str:
        key = m.group(1)
        if key in params:
            return str(params[key])
        return m.group(0) if ":" not in m.group(0) else key

    return _PH.sub(sub, template)


@dataclass
class Diag:
    """One diagnostic. `severity` is error, warning, panic or refused (host refusal)."""

    code: str
    severity: str
    what: str
    why: str
    try_: str
    file: str = ""
    line: int = 0
    column: int = 0
    readings: list[str] = field(default_factory=list)
    trace: list[str] = field(default_factory=list)
    title: str = ""

    def to_json(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "code": self.code,
            "severity": "error" if self.severity == "refused" else self.severity,
            "file": self.file,
            "line": self.line,
            "column": self.column,
            "end_line": self.line,
            "end_column": self.column,
            "what": self.what,
            "why": self.why,
            "try": self.try_,
        }
        if self.readings:
            d["readings"] = self.readings
        if self.trace:
            d["trace"] = self.trace
        return d

    def render(self, source: str | None = None) -> str:
        sev = "error" if self.severity == "refused" else self.severity
        out = [f"{sev}[{self.code}]: {self.title}"]
        out.append(f"  --> {self.file or '<input>'}:{self.line}:{max(self.column, 1)}")
        if source is not None and self.line > 0:
            lines = source.splitlines()
            if self.line <= len(lines):
                text = lines[self.line - 1]
                if self.column <= 0:
                    self.column = len(text) - len(text.lstrip()) + 1
                num = str(self.line)
                pad = " " * len(num)
                out.append(f" {pad} |")
                out.append(f" {num} | {lines[self.line - 1]}")
                out.append(f" {pad} | {' ' * (max(self.column, 1) - 1)}^")
        for t in self.trace:
            out.append(f"  at {t}")
        out.append(f" what: {self.what}")
        for i, r in enumerate(self.readings, 1):
            out.append(f"       ({i}) {r}")
        out.append(f"  why: {self.why}")
        out.append(f"  try: {self.try_}")
        return "\n".join(out)


def make(
    code: str,
    line: int = 0,
    column: int = 0,
    severity: str | None = None,
    readings: list[str] | None = None,
    **params: Any,
) -> Diag:
    """Build a diagnostic for `code` (with or without the `SAY-` prefix)."""
    if not code.startswith("SAY-"):
        code = "SAY-" + code
    kind, meaning, what, why, try_ = CODES[code]
    # Template placeholders that clash with the location arguments are passed as at_<name>.
    params = {(k[3:] if k.startswith("at_") else k): v for k, v in params.items()}
    if severity is None:
        severity = {"E": "error", "W": "warning", "P": "panic", "H": "refused"}.get(kind[0], "error")
        if kind == "E/P":
            severity = "error"
    return Diag(
        code=code,
        severity=severity,
        title=meaning,
        what=params.pop("what", None) or _fill(what, params),
        why=params.pop("why", None) or _fill(why, params),
        try_=params.pop("try_", None) or _fill(try_, params),
        line=line,
        column=column,
        readings=readings or [],
    )


class SayError(Exception):
    """A diagnostic raised as an exception (compile error, panic, or host refusal)."""

    def __init__(
        self,
        code: str,
        line: int = 0,
        column: int = 0,
        severity: str | None = None,
        readings: list[str] | None = None,
        **params: Any,
    ) -> None:
        self.diag = make(code, line, column, severity, readings, **params)
        super().__init__(f"{self.diag.code}: {self.diag.what}")

    @property
    def code(self) -> str:
        return self.diag.code


def panic(code: str, line: int = 0, **params: Any) -> SayError:
    return SayError(code, line, severity="panic", **params)


class Sink:
    """Collects warnings (and non-fatal errors) in report order."""

    def __init__(self) -> None:
        self.items: list[Diag] = []

    def warn(self, code: str, line: int = 0, column: int = 0, **params: Any) -> None:
        self.items.append(make(code, line, column, severity="warning", **params))

    def add(self, d: Diag) -> None:
        self.items.append(d)

    def errors(self) -> list[Diag]:
        return [d for d in self.items if d.severity != "warning"]


def dumps(diags: list[Diag]) -> str:
    return json.dumps(
        {"version": "say-json/1", "diagnostics": [d.to_json() for d in diags]}, ensure_ascii=False, indent=2
    )
