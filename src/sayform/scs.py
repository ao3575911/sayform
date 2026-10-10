"""Canonical serialisation SCS-1 and the BLAKE3 core hash (spec/04-core-ast.md sections 5-6).

Where the spec leaves a byte choice open, the choice is marked `spec-gap` here:
- Interp text parts carry the byte 0x00 before the text (other parts are tagged nodes);
- a quantity's number carries 0x00 (integer) or 0x01 (decimal) before it.
"""

from __future__ import annotations

import base64
import struct
import unicodedata
from dataclasses import fields
from decimal import Decimal
from fractions import Fraction
from typing import Any

from blake3 import blake3

from . import core as C
from .diagnostics import SayError

HEADER = b"sayform/core/1\x00"
#: (node class name, field) pairs that are optional (`T?` in the catalogue).
OPTIONAL = {
    ("Use", "names"), ("Use", "alias"), ("Use", "foreign"), ("Func", "result"), ("Param", "slot"),
    ("Param", "type"), ("Param", "default"), ("TParam", "role"), ("FieldDef", "default"),
    ("Check", "label"), ("Check", "expected"), ("Check", "body"), ("Bind", "type"), ("If", "else_"),
    ("Match", "else_"), ("MCase", "guard"), ("Return", "value"), ("Narrow", "arg"), ("Child", "label"),
    ("RecordLit", "base"), ("PBind", "type"), ("PList", "rest"), ("TMoney", "currency"),
    ("Rule", "guard"), ("Func", "explained"),
}  # fmt: skip
PAIRS = {"slots", "pairs"}
REF_KINDS = {"local": 0, "def": 1, "builtin": 2, "foreign": 3, "patvar": 4, "scc": 5}


def leb(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def text(s: str) -> bytes:
    b = unicodedata.normalize("NFC", s).encode("utf-8")
    return leb(len(b)) + b


def integer(n: int) -> bytes:
    mag = abs(n)
    raw = mag.to_bytes((mag.bit_length() + 7) // 8, "big") if mag else b""
    return (b"\x01" if n < 0 else b"\x00") + leb(len(raw)) + raw


def decimal(d: Decimal) -> bytes:
    sign, digits, exp = d.as_tuple()
    coef = int("".join(map(str, digits)) or "0") * (-1 if sign else 1)
    return integer(coef) + integer(int(exp))


class Encoder:
    def __init__(self, def_hashes: dict[str, bytes] | None = None, scc: dict[str, int] | None = None) -> None:
        self.def_hashes = def_hashes or {}
        self.scc = scc or {}

    def ref(self, r: C.Ref) -> bytes:
        k = r.kind
        if k == "def" and r.value in self.scc:
            return b"\x05" + leb(self.scc[r.value])
        if k == "def":
            return b"\x01" + self.def_hashes.get(str(r.value), b"\x00" * 32)
        if k in ("local", "patvar", "scc"):
            return bytes([REF_KINDS[k]]) + leb(int(r.value))
        if k == "foreign":
            return b"\x03" + b"".join(text(str(x)) for x in r.value)
        return b"\x02" + text(str(r.value))

    def lit(self, n: C.Lit) -> bytes:
        k, v = n.kind, n.value
        out = bytes([n.TAG]) + text(k)
        if k == "integer":
            return out + integer(v)
        if k == "decimal":
            return out + decimal(v)
        if k == "rational":
            f = Fraction(v)
            return out + integer(f.numerator) + integer(f.denominator)
        if k == "approx":
            return out + struct.pack(">d", float(v))
        if k == "text":
            return out + text(v)
        if k == "truth":
            return out + (b"\x01" if v else b"\x00")
        if k == "quantity":
            num, unit = v
            numb = b"\x01" + decimal(num) if isinstance(num, Decimal) else b"\x00" + integer(num)
            return out + numb + text(unit)
        return out

    def value(self, v: Any, owner: str = "", fname: str = "") -> bytes:
        if v is None:
            return b"\x00"
        if (owner, fname) in OPTIONAL:
            return b"\x01" + self.value(v, "", fname)
        if isinstance(v, bool):
            return b"\x01" if v else b"\x00"
        if isinstance(v, int):
            return integer(v)
        if isinstance(v, str):
            return text(v)
        if isinstance(v, C.Ref):
            return self.ref(v)
        if isinstance(v, tuple):
            if fname in PAIRS or (fname == "fields" and owner in ("RecordLit", "PRecord", "PCase")):
                return leb(len(v)) + b"".join(self.value(a) + self.value(b) for a, b in v)
            if fname == "parts":
                return leb(len(v)) + b"".join(b"\x00" + text(x) if isinstance(x, str) else self.node(x) for x in v)
            return leb(len(v)) + b"".join(self.value(x) for x in v)
        return self.node(v)

    def node(self, n: Any, omit_name: bool = False) -> bytes:
        if isinstance(n, C.Lit):
            return self.lit(n)
        name = type(n).__name__
        tag = getattr(n, "TAG", None)
        is_struct = isinstance(n, C.STRUCTS)
        if not tag and not is_struct:
            raise SayError("E1002", 0, 0, tag=name)
        out = bytearray() if is_struct else bytearray([int(tag or 0)])
        for f in fields(n):
            if not f.compare:
                continue
            v = getattr(n, f.name)
            if f.name == "name" and (omit_name or name == "Name"):
                continue  # symbol names in Name are omitted; only ref is encoded
            if name in ("PBind",) and f.name == "name":
                continue  # local binder names are excluded (the ref carries the index)
            if name == "Param" and f.name == "name" and n.slot != "with":
                continue  # positional and slot parameter names are local; named ones are interface
            out += self.value(v, name, f.name)
        return bytes(out)


def b3(data: bytes) -> bytes:
    return blake3(data).digest()


def show_hash(h: bytes) -> str:
    return "b3:" + base64.b32encode(h).decode().rstrip("=").lower()


def def_name(d: Any) -> str | None:
    if isinstance(d, (C.Func, C.RecordDef, C.VariantDef, C.Ruleset)):
        return d.name
    if isinstance(d, C.Bind) and isinstance(d.target, C.PBind):
        return d.target.name
    return None


def deps(d: Any) -> set[str]:
    return {str(x.ref.value) for x in C.walk(d) if isinstance(x, C.Name) and x.ref.kind == "def"}


def encode_def(d: Any, enc: Encoder) -> bytes:
    return enc.node(d, omit_name=isinstance(d, C.Func))  # a function's own name is not hashed


def hash_module(m: C.Module) -> tuple[dict[str, bytes], bytes]:
    """Return (definition hashes by export name, module hash)."""
    header = HEADER + leb(m.edition)
    defs = {n: d for d in m.body if (n := def_name(d)) is not None}
    graph = {n: deps(d) & set(defs) for n, d in defs.items()}
    hashes: dict[str, bytes] = {}
    for comp in sccs(graph):
        enc = Encoder(hashes)
        if len(comp) == 1 and comp[0] not in graph[comp[0]]:
            hashes[comp[0]] = b3(header + encode_def(defs[comp[0]], enc))
            continue
        probe = Encoder(hashes, {n: 0 for n in comp})
        order = sorted(comp, key=lambda n: encode_def(defs[n], probe))
        enc = Encoder(hashes, {n: i for i, n in enumerate(order)})
        blob = leb(len(order)) + b"".join(encode_def(defs[n], enc) for n in order)
        ch = b3(header + blob)
        for i, n in enumerate(order):
            hashes[n] = b3(ch + leb(i))
    pairs = sorted(hashes.items())
    mh = b3(header + leb(len(pairs)) + b"".join(text(k) + v for k, v in pairs))
    return hashes, mh


def sccs(graph: dict[str, set[str]]) -> list[list[str]]:
    """Tarjan's algorithm; components come out dependencies-first, deterministically."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on: set[str] = set()
    out: list[list[str]] = []

    def visit(v: str) -> None:
        index[v] = low[v] = len(index)
        stack.append(v)
        on.add(v)
        for w in sorted(graph[v]):
            if w not in index:
                visit(w)
                low[v] = min(low[v], low[w])
            elif w in on:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = []
            while True:
                w = stack.pop()
                on.discard(w)
                comp.append(w)
                if w == v:
                    break
            out.append(sorted(comp))

    for v in sorted(graph):
        if v not in index:
            visit(v)
    return out


def serialise(n: Any, edition: int = 0) -> bytes:
    """SCS-1 bytes of a tree with header (used by `say core --scs` and HASH-11)."""
    return HEADER + leb(edition) + Encoder().node(n)


def to_json(n: Any) -> Any:
    """Stable JSON form of a core tree (`say core --json`, schema say-json/1)."""
    if isinstance(n, C.Lit):
        v = n.value
        if n.kind in ("decimal", "rational", "approx"):
            v = str(v) if n.kind != "approx" else repr(float(v))
        elif n.kind == "quantity":
            v = [str(v[0]), v[1]]
        return {"node": "Lit", "kind": n.kind, "value": v}
    if isinstance(n, C.Ref):
        return {"kind": n.kind, "value": n.value if not isinstance(n.value, tuple) else list(n.value)}
    if isinstance(n, tuple):
        return [to_json(x) for x in n]
    if isinstance(n, C.Node) or isinstance(n, C.STRUCTS):
        out: dict[str, Any] = {"node": type(n).__name__}
        for f in fields(n):
            if f.compare:
                out[f.name.rstrip("_")] = to_json(getattr(n, f.name))
        return out
    return n
