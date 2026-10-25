"""Writes cent/_api.py from proto/api.proto.

The request and result types of every Centrifugo server API method, as
dataclasses, and the methods of Client, AsyncClient, Batch and AsyncBatch
sending them:

    python gen/generate.py            # write
    python gen/generate.py --check    # fail when the committed file is stale

The output is committed. `make generate-check` runs the check in CI.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from proto import Field, Message, Schema, parse

ROOT = Path(__file__).resolve().parent.parent

# rpc calls server API extensions, which neither Centrifugo OSS nor PRO
# provides.
OMITTED_COMMANDS = {"rpc"}

# Messages written by hand (BroadcastResult: a result per channel; Error: an
# exception), only used on the wire (the batch envelope), or wrappers which
# become optional scalars.
HANDWRITTEN = {"Error", "BroadcastResult"}
WIRE_ONLY = {"Command", "Reply", "BatchRequest", "BatchResponse"}
WRAPPERS = {"BoolValue": "bool", "Int32Value": "int"}

PY_TYPES = {
    "string": ("str", '""'),
    "bool": ("bool", "False"),
    "int32": ("int", "0"),
    "int64": ("int", "0"),
    "uint32": ("int", "0"),
    "uint64": ("int", "0"),
    "double": ("float", "0.0"),
    "float": ("float", "0.0"),
}
DECODERS = {
    "string": "_w.c_str",
    "bool": "_w.c_bool",
    "int32": "_w.c_int",
    "int64": "_w.c_int",
    "uint32": "_w.c_int",
    "uint64": "_w.c_int",
    "double": "_w.c_float",
    "float": "_w.c_float",
    "bytes": "_w.c_json",
}


class Command:
    def __init__(self, method: str, request: Message, result: str, pro_only: bool) -> None:
        self.method = method
        self.request = request
        self.result = result
        self.pro_only = pro_only


def commands(s: Schema) -> list[Command]:
    cmd, reply = s.by_name.get("Command"), s.by_name.get("Reply")
    if cmd is None or reply is None:
        raise SystemExit("api.proto: Command and Reply messages are required")
    results = {f.name: f.type for f in reply.fields}
    out = []
    for f in cmd.fields:
        if f.name in OMITTED_COMMANDS:
            continue
        req = s.by_name.get(f.type)
        if req is None or f.name not in results:
            raise SystemExit(f"api.proto: Command.{f.name} has no request message or no Reply.{f.name}")
        want = "".join(p.capitalize() for p in f.name.split("_")) + "Request"
        if f.type.lower() != want.lower():
            raise SystemExit(f"api.proto: Command.{f.name} is {f.type}, expected {want}")
        out.append(Command(f.name, req, results[f.name], "Centrifugo PRO only" in " ".join(f.doc)))
    return out


def skipped(s: Schema, cmds: list[Command]) -> set[str]:
    names = set(HANDWRITTEN) | WIRE_ONLY | set(WRAPPERS)
    names |= {rpc.response for rpc in s.methods}  # the error-or-result envelopes
    for c in ("Command", "Reply"):
        for f in s.by_name[c].fields:
            if f.name in OMITTED_COMMANDS:
                names.add(f.type)
    return names


def field_type(f: Field) -> tuple[str, str]:
    """The Python annotation and default of a field."""
    if f.type in WRAPPERS:
        base, default = f"{WRAPPERS[f.type]} | None", "None"
    elif f.type == "bytes":
        base, default = "JSON", "None"
    elif f.type in PY_TYPES:
        base, default = PY_TYPES[f.type]
    else:
        base, default = f"{f.type} | None", "None"
    if f.map_key:
        inner = base.removesuffix(" | None")
        return f"dict[str, {inner}]", "field(default_factory=dict)"
    if f.repeated:
        inner = base.removesuffix(" | None")
        return f"list[{inner}]", "field(default_factory=list)"
    return base, default


def encoder(f: Field) -> list[str]:
    """Lines of _to_wire setting w[f.name] when the field is not zero."""
    n, key = f"self.{f.name}", repr(f.name)
    t = f.type
    if f.map_key:
        if t == "bytes":
            value = f"{{k: _w.payload(v, {key} + '[' + repr(k) + ']') for k, v in {n}.items()}}"
        elif t in PY_TYPES:
            value = f"dict({n})"
        else:
            value = f"{{k: v._to_wire() for k, v in {n}.items()}}"
        return [f"if {n}:", f"    w[{key}] = {value}"]
    if f.repeated:
        if t == "bytes":
            value = f"[_w.payload(v, f'{f.name}[{{i}}]') for i, v in enumerate({n})]"
        elif t in PY_TYPES:
            value = f"list({n})"
        else:
            value = f"[v._to_wire() for v in {n}]"
        return [f"if {n}:", f"    w[{key}] = {value}"]
    if t in WRAPPERS:
        return [f"if {n} is not None:", f"    w[{key}] = {{'value': {n}}}"]
    if t == "bytes":
        return [f"if {n} is not None:", f"    w[{key}] = _w.payload({n}, {key})"]
    if t in PY_TYPES:
        return [f"if {n}:", f"    w[{key}] = {n}"]
    # A nested message, left out when nothing in it is set.
    return [f"if {n} is not None and (v := {n}._to_wire()):", f"    w[{key}] = v"]


def decoder(f: Field, owner: str) -> str:
    """The expression of _from_wire decoding f from the dict d."""
    key, where = repr(f.name), repr(f"{owner}.{f.name}")
    t = f.type
    if t in WRAPPERS:
        conv = "_w.c_bool" if WRAPPERS[t] == "bool" else "_w.c_int"
        return f"_w.wrapper(d, {key}, {where}, {conv})"
    conv = DECODERS.get(t, f"{t}._from_wire")
    if f.map_key:
        return f"_w.dict_of(d, {key}, {where}, {conv})"
    if f.repeated:
        return f"_w.list_of(d, {key}, {where}, {conv})"
    if t in DECODERS:
        if t == "bytes":
            return f"d.get({key})"
        return f"_w.scalar(d, {key}, {where}, {conv}, {PY_TYPES[t][1]})"
    return f"_w.message(d, {key}, {where}, {conv})"


def docstring(lines: list[str], indent: str) -> list[str]:
    if not lines:
        return []
    text = "\n".join(lines).replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    if len(lines) == 1:
        return [f'{indent}"""{text}"""']
    body = textwrap.indent(text, indent).splitlines()
    return [f'{indent}"""{body[0].lstrip()}', *[b.rstrip() for b in body[1:]], f'{indent}"""']


def method_doc(c: Command) -> list[str]:
    """ "PublishRequest publishes data into a channel." -> "Publishes data into a channel." """
    doc = list(c.request.doc)
    prefix = c.request.name + " "
    if doc and doc[0].startswith(prefix):
        rest = doc[0][len(prefix) :]
        doc[0] = rest[:1].upper() + rest[1:]
    if not doc:
        doc = [f"Calls the {c.method} method of the Centrifugo server API."]
    return doc


def emit_message(out: list[str], m: Message, api_method: str | None, protocol: str) -> None:
    """A message as a dataclass, with its _to_wire and _from_wire."""
    p = out.append
    p("")
    p("")
    p("@dataclass(slots=True, kw_only=True)")
    p(f"class {m.name}:")
    doc = m.doc or [f"{m.name} is the {m.name} message of the Centrifugo {protocol}."]
    out.extend(docstring(doc, "    "))
    if api_method is not None:
        p("")
        p(f"    API_METHOD: ClassVar[str] = {api_method!r}")
        p('    """The server API method the request is sent to."""')
    for f in m.fields:
        ann, default = field_type(f)
        p("")
        p(f"    {f.name}: {ann} = {default}")
        out.extend(docstring(f.doc, "    "))
    p("")
    p("    def _to_wire(self) -> dict[str, Any]:")
    if not m.fields:
        p("        return {}")
    else:
        p("        w: dict[str, Any] = {}")
        for f in m.fields:
            out.extend("        " + line for line in encoder(f))
        p("        return w")
    p("")
    p("    @classmethod")
    p(f"    def _from_wire(cls, v: Any, where: str = {m.name!r}) -> {m.name}:")
    if not m.fields:
        p("        _w.obj(v, where)")
        p("        return cls()")
    else:
        p("        d = _w.obj(v, where)")
        p("        return cls(")
        for f in m.fields:
            p(f"            {f.name}={decoder(f, m.name)},")
        p("        )")


def proxy_messages(s: Schema) -> list[Message]:
    """The messages the methods which are not streaming use, directly or through
    their fields - but the envelopes, which the handlers build, Error and
    Disconnect, which are exceptions, and the wrappers."""
    used: set[str] = set()

    def visit(name: str) -> None:
        m = s.by_name.get(name)
        if m is None or name in used:
            return
        used.add(name)
        for f in m.fields:
            visit(f.type)

    envelopes = set()
    for rpc in s.methods:
        if not rpc.streaming:
            visit(rpc.request)
            visit(rpc.response)
            envelopes.add(rpc.response)
    skip = envelopes | {"Error", "Disconnect"} | set(WRAPPERS)
    return [m for m in s.messages if m.name in used and m.name not in skip]


def generate_proxy(s: Schema) -> str:
    msgs = proxy_messages(s)
    out: list[str] = []
    p = out.append
    p("# Code generated by gen/generate.py from proto/proxy.proto. DO NOT EDIT.")
    p('"""The requests and results of the Centrifugo proxy protocol."""')
    p("")
    p("from __future__ import annotations")
    p("")
    p("from dataclasses import dataclass, field")
    p("from typing import Any")
    p("")
    p("from cent import _wire as _w")
    p("from cent._payload import JSON")
    p("")
    p("__all__ = [")
    for name in sorted(m.name for m in msgs):
        p(f"    {name!r},")
    p("]")
    for m in msgs:
        emit_message(out, m, None, "proxy protocol")
    p("")
    return "\n".join(out)


def generate(s: Schema) -> str:
    cmds = commands(s)
    skip = skipped(s, cmds)
    out: list[str] = []
    p = out.append
    p("# Code generated by gen/generate.py from proto/api.proto. DO NOT EDIT.")
    p('"""The request and result types of the Centrifugo server API."""')
    p("")
    p("from __future__ import annotations")
    p("")
    p("from dataclasses import dataclass, field")
    p("from typing import TYPE_CHECKING, Any, ClassVar, TypeVar")
    p("")
    p("from cent import _wire as _w")
    p("from cent._payload import JSON")
    p("")
    p("if TYPE_CHECKING:")
    p("    from cent._batch import Pending")
    p("")
    p('_R = TypeVar("_R")')
    public = [m.name for m in s.messages if m.name not in skip] + ["Request"]
    p("")
    p("__all__ = [")
    for name in sorted(public):
        p(f"    {name!r},")
    p("]")

    requests = {c.request.name: c.method for c in cmds}
    for m in s.messages:
        if m.name in skip:
            continue
        emit_message(out, m, requests.get(m.name), "server API")

    p("")
    p("")
    p("Request = (")
    for i, c in enumerate(cmds):
        p(f"    {'| ' if i else ''}{c.request.name}")
    p(")")
    p('"""Any request of the server API: what Client methods and new_command take."""')
    p("")
    p("# Every API method, batch included, and whether only Centrifugo PRO has it.")
    p("METHODS: dict[str, bool] = {")
    p('    "batch": False,')
    for c in cmds:
        p(f"    {c.method!r}: {c.pro_only},")
    p("}")
    p("")
    p("# Every request type.")
    p("REQUESTS: frozenset[type[Any]] = frozenset({")
    for c in cmds:
        p(f"    {c.request.name},")
    p("})")

    for kind in ("sync", "async", "batch"):
        p("")
        p("")
        if kind == "sync":
            p("class _ClientAPI:")
            p('    """The server API methods of Client."""')
            p("")
            p("    if TYPE_CHECKING:")
            p("")
            p("        def _invoke(self, request: Any, result: type[_R], timeout: float | None) -> _R: ...")
        elif kind == "async":
            p("class _AsyncClientAPI:")
            p('    """The server API methods of AsyncClient."""')
            p("")
            p("    if TYPE_CHECKING:")
            p("")
            p("        async def _invoke(self, request: Any, result: type[_R], timeout: float | None) -> _R: ...")
        else:
            p("class _BatchAPI:")
            p('    """The commands of Batch and AsyncBatch."""')
            p("")
            p("    if TYPE_CHECKING:")
            p("")
            p("        def _add(self, request: Any, result: type[_R]) -> Pending[_R]: ...")
        for c in cmds:
            if c.method == "broadcast":
                continue  # written by hand: its result is a result per channel
            req, res = c.request.name, c.result
            empty = not c.request.fields
            arg = f"request: {req} | None = None" if empty else f"request: {req}"
            value = f"request or {req}()" if empty else "request"
            doc = method_doc(c)
            if c.pro_only and not any("Centrifugo PRO only" in line for line in doc):
                doc.append("Centrifugo PRO only.")
            p("")
            if kind == "batch":
                p(f"    def {c.method}(self, {arg}) -> Pending[{res}]:")
                out.extend(
                    docstring(
                        [f"Adds a {c.method} command; its outcome is what Client.{c.method} would return."], "        "
                    )
                )
                p(f"        return self._add({value}, {res})")
                continue
            sig = f"self, {arg}, *, timeout: float | None = None"
            if kind == "async":
                p(f"    async def {c.method}({sig}) -> {res}:")
                out.extend(docstring(doc, "        "))
                p(f"        return await self._invoke({value}, {res}, timeout)")
            else:
                p(f"    def {c.method}({sig}) -> {res}:")
                out.extend(docstring(doc, "        "))
                p(f"        return self._invoke({value}, {res}, timeout)")
    p("")
    return "\n".join(out)


def format_code(code: str, path: Path) -> str:
    """code as ruff formats it, so that the committed file passes the lint."""
    proc = subprocess.run(  # noqa: S603 - our own ruff, from the venv
        [sys.executable, "-m", "ruff", "format", "--stdin-filename", str(path), "-"],
        input=code,
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
    )
    if proc.returncode != 0:
        raise SystemExit(f"ruff format failed: {proc.stderr}")
    return proc.stdout


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="fail when the generated code is stale")
    args = ap.parse_args()
    outputs = [
        ("api.proto", ROOT / "cent" / "_api.py", generate),
        ("proxy.proto", ROOT / "cent" / "proxy" / "_types.py", generate_proxy),
    ]
    stale = []
    for proto_name, out_path, gen in outputs:
        src_path = ROOT / "proto" / proto_name
        code = format_code(gen(parse(src_path.read_text(), src_path.name)), out_path)
        if args.check:
            if not out_path.exists() or out_path.read_text() != code:
                stale.append(str(out_path.relative_to(ROOT)))
            continue
        out_path.parent.mkdir(exist_ok=True)
        out_path.write_text(code)
    if stale:
        raise SystemExit(f"stale generated code: {', '.join(stale)}: run `make generate`")


if __name__ == "__main__":
    main()
