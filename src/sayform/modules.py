"""Module loading (spec/10-modules-dialects.md section 1): `shop.cart` lives at `shop/cart.say`
under the package root (the directory holding `say.toml`, else the file's directory); imports
load depth-first in a fixed order and cycles are SAY-E0701."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import core as C
from .diagnostics import SayError, Sink


def package_root(path: Path) -> Path:
    for d in path.resolve().parents:
        if (d / "say.toml").exists():
            return d
    return path.resolve().parent


def e0701(line: int, what: str) -> SayError:
    e = SayError("E0701", line, m="", p="", cycle="")
    e.diag.what = what
    return e


def load_tree(path: str, sink: Sink | None = None) -> tuple[C.Module, list[C.Module]]:
    """Parse `path` and everything it uses; returns the root module and its dependencies in
    load order (dependencies first)."""
    from .parser import parse

    root, done, order = package_root(Path(path)), set[str](), list[C.Module]()

    def visit(file: Path, name: str, stack: list[str]) -> C.Module:
        mod = parse(file.read_text(encoding="utf-8"), str(file), sink, name=name)
        if stack and mod.name != name:
            raise e0701(1, f"Module name `{mod.name}` does not match path `{file.relative_to(root)}`.")
        full = [*stack, name]
        for u in mod.uses:
            if u.path in full:
                raise e0701(u.line, "Import cycle " + " -> ".join([*full[full.index(u.path) :], u.path]) + ".")
            dep = root / (u.path.replace(".", "/") + ".say")
            if u.path not in done:
                if not dep.exists():
                    raise e0701(u.line, f"Module `{u.path}` not found at `{dep.relative_to(root)}`.")
                order.append(visit(dep, u.path, full))
                done.add(u.path)
        return mod

    main = visit(Path(path), Path(path).stem, [])
    return main, order


def link(ev: Any, mod: C.Module, deps: list[C.Module], run: Any) -> None:
    """Load dependencies into the evaluator and bind `use` names (edition 0 exports every
    top-level definition). One flat namespace: a name defined by two modules is SAY-E0404."""
    owner: dict[str, str] = {}
    exports: dict[str, list[str]] = {}
    for m in [*deps, mod]:
        before = set(ev.globals) | set(ev.types)
        run(ev.load(m))
        new = sorted((set(ev.globals) | set(ev.types)) - before)
        for d in m.body:
            name = getattr(d, "name", None)
            if isinstance(d, (C.Func, C.RecordDef, C.VariantDef)) and name in owner and name not in new:
                raise SayError("E0404", d.line, name=name, a=f"module {owner[name]}", b=f"module {m.name}")
        owner.update({n: m.name for n in new})
        exports[m.name] = new
        for u in m.uses:
            prefix = u.alias or u.path.split(".")[-1]
            for n in exports.get(u.path, []):
                ev.globals[f"{prefix}.{n}"] = ev.globals.get(n, ev.types.get(n))
