"""Writes API.md, the API reference, from cent's docstrings:

    python gen/api_docs.py            # write
    python gen/api_docs.py --check    # fail when API.md is stale

It reads the source rather than the imported objects, for the docstrings of
fields - a string literal under an attribute - which Python does not keep.
"""

from __future__ import annotations

import argparse
import ast
import inspect
import sys
import textwrap
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import cent  # noqa: E402
from cent import endpoints, proxy, sharedpoll, token  # noqa: E402

_trees: dict[str, ast.Module] = {}


def tree(module: str) -> ast.Module:
    if module not in _trees:
        path = Path(inspect.getfile(sys.modules[module]))
        _trees[module] = ast.parse(path.read_text())
    return _trees[module]


def find_class(obj: type) -> ast.ClassDef | None:
    for node in ast.walk(tree(obj.__module__)):
        if isinstance(node, ast.ClassDef) and node.name == obj.__name__:
            return node
    return None


def find_function(module: str, qualname: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    parts = qualname.split(".")
    body: list[ast.stmt] = tree(module).body
    for i, part in enumerate(parts):
        for node in body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == part:
                if i == len(parts) - 1:
                    return node if not isinstance(node, ast.ClassDef) else None
                if isinstance(node, ast.ClassDef):
                    body = node.body
                break
        else:
            return None
    return None


def doc(text: str | None) -> str:
    """A docstring as Markdown: doctest lines and "::" blocks become code."""
    if not text:
        return ""
    out: list[str] = []
    code: list[str] = []
    lines = textwrap.dedent(text).strip("\n").splitlines()
    in_block = False

    def flush() -> None:
        if code:
            block = textwrap.dedent("\n".join(code)).strip("\n").splitlines()
            out.extend(["", "```python", *block, "```", ""])
            code.clear()

    for line in lines:
        if line.startswith((">>> ", "... ")):
            code.append(line[4:])
            continue
        if in_block:
            if line.startswith("    ") or not line.strip():
                code.append(line)
                continue
            in_block = False
        flush()
        if line.rstrip().endswith("::"):
            out.append(line.rstrip()[:-1])
            in_block = True
            continue
        out.append(line)
    flush()
    return "\n".join(out).strip()


def signature(node: ast.FunctionDef | ast.AsyncFunctionDef, name: str, drop_self: bool) -> str:
    args = node.args
    if drop_self and args.args and args.args[0].arg in ("self", "cls"):
        args = ast.arguments(
            posonlyargs=args.posonlyargs,
            args=args.args[1:],
            vararg=args.vararg,
            kwonlyargs=args.kwonlyargs,
            kw_defaults=args.kw_defaults,
            kwarg=args.kwarg,
            defaults=args.defaults,
        )
    ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
    prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
    params = ast.unparse(args)
    one_line = f"{prefix}{name}({params}){ret}"
    if len(one_line) <= 100:
        return one_line
    lines = "".join(f"\n    {p}," for p in _split_params(params))
    return f"{prefix}{name}({lines}\n){ret}"


def _split_params(params: str) -> list[str]:
    """params split at the commas outside brackets."""
    out, depth, cur = [], 0, ""
    for ch in params:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
            continue
        cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def fields(node: ast.ClassDef) -> list[tuple[str, str, str]]:
    """(name, annotation and default, docstring) of a class's public attributes."""
    out = []
    body = node.body
    for i, stmt in enumerate(body):
        if not isinstance(stmt, ast.AnnAssign) or not isinstance(stmt.target, ast.Name):
            continue
        name = stmt.target.id
        ann = ast.unparse(stmt.annotation)
        if name.startswith("_") or ann.startswith("ClassVar"):
            continue
        value = f" = {ast.unparse(stmt.value)}" if stmt.value is not None else ""
        value = value.replace("field(default_factory=list)", "[]").replace("field(default_factory=dict)", "{}")
        text = ""
        nxt = body[i + 1] if i + 1 < len(body) else None
        if isinstance(nxt, ast.Expr) and isinstance(nxt.value, ast.Constant) and isinstance(nxt.value.value, str):
            text = nxt.value.value
        out.append((name, ann + value, text))
    return out


def methods(cls: type) -> list[str]:
    """Public methods and properties of cls, the inherited ones from cent included."""
    out = []
    seen: set[str] = set()
    for klass in cls.__mro__:
        if not klass.__module__.startswith("cent"):
            continue
        for name, member in vars(klass).items():
            if name.startswith("_") or name in seen:
                continue
            seen.add(name)
            func = member.fget if isinstance(member, property) else getattr(member, "__func__", member)
            if not callable(func) or isinstance(member, type):
                continue
            node = find_function(klass.__module__, f"{klass.__qualname__}.{name}")
            if node is None:
                continue
            sig = signature(node, name, drop_self=not isinstance(member, staticmethod))
            if isinstance(member, property):
                sig = f"{name}  (property)"
            text = doc(ast.get_docstring(node))
            out.append(f"#### `{sig}`\n\n{text}".rstrip())
    return sorted(out)


def render_class(cls: type, level: str = "###") -> str:
    node = find_class(cls)
    head = f"{level} `{cls.__name__}`"
    if node is None:
        return head
    parts = [head]
    init = find_function(cls.__module__, f"{cls.__qualname__}.__init__")
    if init is not None:
        parts.append(f"```python\n{signature(init, cls.__name__, drop_self=True)}\n```")
    if text := doc(ast.get_docstring(node)):
        parts.append(text)
    fs = fields(node)
    if fs:
        rows = []
        for name, ann, text in fs:
            first = " ".join(text.split()) if text else ""
            rows.append(f"- `{name}: {ann}`" + (f" - {first}" if first else ""))
        parts.append("\n".join(rows))
    parts.extend(methods(cls))
    return "\n\n".join(parts)


def render_function(obj: Any) -> str:
    node = find_function(obj.__module__, obj.__qualname__)
    if node is None:
        return f"### `{obj.__name__}`"
    return f"### `{signature(node, obj.__name__, drop_self=False)}`\n\n{doc(ast.get_docstring(node))}".rstrip()


def render_value(name: str, module: Any = None) -> str:
    """A module-level constant or type alias, with its docstring: from module,
    or from whichever of cent's modules assigns it."""
    candidates = [module.__name__] if module is not None else sorted(m for m in sys.modules if m.startswith("cent"))
    for mod in candidates:
        found = _render_value(name, mod)
        if found:
            return found
    return f"### `{name}`"


def _render_value(name: str, mod: str) -> str:
    body = tree(mod).body
    for i, stmt in enumerate(body):
        if isinstance(stmt, ast.Assign):
            targets = [t.id for t in stmt.targets if isinstance(t, ast.Name)]
            assigned: ast.expr | None = stmt.value
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            targets = [stmt.target.id]
            assigned = stmt.value
        else:
            continue
        if name not in targets:
            continue
        value = ast.unparse(assigned) if assigned is not None else ""
        nxt = body[i + 1] if i + 1 < len(body) else None
        text = ""
        if isinstance(nxt, ast.Expr) and isinstance(nxt.value, ast.Constant) and isinstance(nxt.value.value, str):
            text = doc(nxt.value.value)
        value = " ".join(value.split())
        if len(value) > 100:
            value = value[:97] + "..."
        return f"### `{name}`\n\n```python\n{name} = {value}\n```\n\n{text}".rstrip()
    return ""


def section(title: str, intro: str, items: list[str]) -> str:
    return "\n\n".join([f"## {title}", intro, *items]) if intro else "\n\n".join([f"## {title}", *items])


def generated(title: str, classes: list[type]) -> str:
    body = "\n\n".join(render_class(c, "####") for c in classes)
    return f"## {title}\n\n<details>\n<summary>{len(classes)} types</summary>\n\n{body}\n\n</details>"


def is_class(obj: Any) -> bool:
    """A class of cent's: typing.Any, which JSON is, is one too in Python, but an alias here."""
    return inspect.isclass(obj) and obj.__module__.startswith("cent")


def is_generated(obj: Any) -> bool:
    return inspect.isclass(obj) and obj.__module__ in ("cent._api", "cent.proxy._types")


def generate() -> str:
    out = [
        "# cent API reference",
        "<!-- Generated by gen/api_docs.py from cent's docstrings: `make docs`. Do not edit. -->",
        "The public API of cent, from its docstrings. The [README](README.md) shows how to use it; "
        "the request and result types come from Centrifugo's protos, with their documentation.",
    ]

    names = list(cent.__all__)
    objs = {n: getattr(cent, n) for n in names}
    errors = [o for o in objs.values() if is_class(o) and issubclass(o, BaseException)]
    hand_classes = [
        o for o in objs.values() if is_class(o) and not issubclass(o, BaseException) and not is_generated(o)
    ]
    order = ["Client", "AsyncClient", "AutoBatch", "Batch", "AsyncBatch", "Pending", "BatchResult"]
    hand_classes.sort(key=lambda c: (order.index(c.__name__) if c.__name__ in order else len(order), c.__name__))
    funcs = [o for o in objs.values() if inspect.isfunction(o)]
    values = [n for n in names if not is_class(objs[n]) and not inspect.isfunction(objs[n])]
    gen_types = sorted((o for o in objs.values() if inspect.isclass(o) and is_generated(o)), key=lambda c: c.__name__)

    out.append(section("cent", "The client, batches, results and helpers.", [render_class(c) for c in hand_classes]))
    out.append(section("cent: functions", "", [render_function(f) for f in funcs]))
    out.append(section("cent: types", "", [render_value(n) for n in values]))
    hierarchy = "\n".join(
        f"{'  ' * (len([b for b in e.__mro__ if b in errors]) - 1)}- `{e.__name__}`"
        for e in sorted(errors, key=lambda e: [b.__name__ for b in reversed(e.__mro__) if b in errors])
    )
    out.append(section("cent: errors", hierarchy, [render_class(e) for e in sorted(errors, key=lambda e: e.__name__)]))

    for mod in (token, endpoints, sharedpoll):
        items = []
        for n in mod.__all__:
            o = getattr(mod, n)
            if inspect.isclass(o):
                items.append(render_class(o))
            elif inspect.isfunction(o):
                items.append(render_function(o))
            else:
                items.append(render_value(n, mod))
        out.append(section(f"cent.{mod.__name__.split('.')[-1]}", doc(mod.__doc__), items))

    pnames = [n for n in proxy.__all__ if not is_generated(getattr(proxy, n))]
    items = []
    for n in pnames:
        o = getattr(proxy, n)
        items.append(render_class(o) if inspect.isclass(o) else render_value(n, proxy))
    out.append(section("cent.proxy", doc(proxy.__doc__), items))

    out.append(generated("cent: request and result types", gen_types))
    out.append(
        generated(
            "cent.proxy: request and result types",
            sorted(
                (getattr(proxy, n) for n in proxy.__all__ if is_generated(getattr(proxy, n))), key=lambda c: c.__name__
            ),
        )
    )
    text = "\n\n".join(out)
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    return text.rstrip() + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="fail when API.md is stale")
    args = ap.parse_args()
    path = ROOT / "API.md"
    text = generate()
    if args.check:
        if not path.exists() or path.read_text() != text:
            raise SystemExit("API.md is stale: run `make docs`")
        return
    path.write_text(text)


if __name__ == "__main__":
    main()
