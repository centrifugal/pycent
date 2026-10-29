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
import keyword
import re
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


def required(f: Field) -> bool:
    """Whether the proto marks the field "Required." without a condition -
    "Required unless b64data is set." stays optional (spec 3.3)."""
    return re.search(r"\bRequired\.", " ".join(f.doc)) is not None


def kwargs(m: Message) -> tuple[list[str], list[str]]:
    """The keyword parameters of a request's method, and the arguments building
    the request from them. Lists and maps default to None, made empty."""
    params, args = [], []
    for f in m.fields:
        if keyword.iskeyword(f.name):
            raise SystemExit(f"api.proto: {m.name}.{f.name} is a Python keyword: no keyword argument can carry it")
        ann, default = field_type(f)
        if required(f):
            # No default: a call without it fails as Python fails it, and type
            # checkers and editors show it.
            params.append(f"{f.name}: {ann.removesuffix(' | None')}")
            args.append(f"{f.name}={f.name}")
        elif default.startswith("field("):
            params.append(f"{f.name}: {ann} | None = None")
            empty = "[]" if ann.startswith("list") else "{}"
            args.append(f"{f.name}={f.name} if {f.name} is not None else {empty}")
        else:
            params.append(f"{f.name}: {ann} = {default}")
            args.append(f"{f.name}={f.name}")
    return params, args


def strip_name(f: Field) -> list[str]:
    """A field's proto comment without the name it starts with, as Go's comments
    do: "skip_history skips..." -> "Skips...", "data is the payload" -> "The
    payload", "version, when > 0, is the version" -> "When > 0, the version"."""
    lines = list(f.doc)
    if not lines:
        return lines
    name = re.escape(f.name)
    first = lines[0]
    if m := re.match(rf"^`?{name}`?\s+(?:is|are)\s+(.*)$", first):
        lines[0] = m[1][:1].upper() + m[1][1:]
    elif m := re.match(rf"^`?{name}`?,\s*(.+?),\s+(?:(?:is|are)\s+)?(.*)$", first):
        lines[0] = f"{m[1][:1].upper()}{m[1][1:]}, {m[2]}"
    elif m := re.match(rf"^`?{name}`?\s+([a-z].*)$", first):
        lines[0] = m[1][:1].upper() + m[1][1:]
    return lines


def args_doc(s: Schema, m: Message) -> list[str]:
    """The "Args:" section of a request's method: each field and its doc."""
    if not m.fields:
        return []
    out = ["", "Args:"]
    for f in m.fields:
        text = strip_name(f) or [f"The {f.name} field."]
        out.append(f"    {f.name}: {text[0]}")
        out.extend(f"        {line}" for line in text[1:])
    return out


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
        p(f"    api_method: ClassVar[str] = {api_method!r}")
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


def generate_commands(s: Schema) -> str:
    """cent/_commands.py: a command per API method, from keyword arguments."""
    cmds = commands(s)
    out: list[str] = []
    p = out.append
    p("# Code generated by gen/generate.py from proto/api.proto. DO NOT EDIT.")
    p('"""Commands for Centrifugo\'s async consumers, one per API method."""')
    p("")
    p("from __future__ import annotations")
    p("")
    # The requests, and the types of their fields.
    used = {c.request.name for c in cmds}
    for c in cmds:
        used |= {f.type for f in c.request.fields if f.type in s.by_name and f.type not in WRAPPERS}
    p("from cent._api import (")
    for name in sorted(used):
        p(f"    {name},")
    p(")")
    p("from cent._command import Command, new_command")
    p("from cent._payload import JSON")
    p("")
    p('__all__ = ["Commands", "command"]')
    p("")
    p("")
    p("class Commands:")
    out.extend(
        docstring(
            [
                "Commands for Centrifugo's async consumers, one per API method: each checks",
                "its request as a call does, and encodes it - see Command. Use the instance,",
                "cent.command::",
                "",
                '    cmd = cent.command.publish(channel="news", data={"text": "hi"})',
            ],
            "    ",
        )
    )
    for c in cmds:
        params, args = kwargs(c.request)
        sig = ", ".join(["self", "*", *params]) if params else "self"
        p("")
        p(f"    def {c.method}({sig}) -> Command:")
        out.extend(docstring([f"The {c.method} command.", *args_doc(s, c.request)], "        "))
        p(f"        return new_command({c.request.name}({', '.join(args)}))")
    p("")
    p("")
    p("command = Commands()")
    p('"""The commands for Centrifugo\'s async consumers: cent.command.publish(...) and the like."""')
    p("")
    return "\n".join(out)


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
    p("    from cent._broadcast import BroadcastResult")
    p("    from cent._client import BroadcastAttemptCallback")
    p("")
    p('_R = TypeVar("_R")')
    # The requests are the methods' keyword arguments: their dataclasses are
    # internal. Nested messages and results are public.
    request_names = {c.request.name for c in cmds}
    public = [m.name for m in s.messages if m.name not in skip and m.name not in request_names]
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
    p('"""Any request of the server API."""')
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
            p("        def _broadcast(self, request: BroadcastRequest, timeout: float | None) -> BroadcastResult: ...")
            p("        def _broadcast_with_retry(")
            p("            self, request: BroadcastRequest, max_attempts: int, attempt_timeout: float | None,")
            p("            on_attempt_error: BroadcastAttemptCallback | None, timeout: float | None,")
            p("        ) -> BroadcastResult: ...")
        elif kind == "async":
            p("class _AsyncClientAPI:")
            p('    """The server API methods of AsyncClient."""')
            p("")
            p("    if TYPE_CHECKING:")
            p("")
            p("        async def _invoke(self, request: Any, result: type[_R], timeout: float | None) -> _R: ...")
            p(
                "        async def _broadcast(self, request: BroadcastRequest, timeout: float | None) -> BroadcastResult: ..."
            )
            p("        async def _broadcast_with_retry(")
            p("            self, request: BroadcastRequest, max_attempts: int, attempt_timeout: float | None,")
            p("            on_attempt_error: BroadcastAttemptCallback | None, timeout: float | None,")
            p("        ) -> BroadcastResult: ...")
        elif kind == "batch":
            p("class _BatchAPI:")
            p('    """The commands of Batch and AsyncBatch."""')
            p("")
            p("    if TYPE_CHECKING:")
            p("")
            p("        def _add(self, request: Any, result: type[_R]) -> Pending[_R]: ...")
            p("        def _add_broadcast(self, request: BroadcastRequest) -> Pending[BroadcastResult]: ...")
        for c in cmds:
            req = c.request.name
            res = "BroadcastResult" if c.method == "broadcast" else c.result
            params, args = kwargs(c.request)
            build = f"{req}({', '.join(args)})"
            fdocs = args_doc(s, c.request)
            p("")
            if kind == "batch":
                sig = ", ".join(["self", "*", *params]) if params else "self"
                p(f"    def {c.method}({sig}) -> Pending[{res}]:")
                out.extend(
                    docstring(
                        [f"Adds a {c.method} command; its outcome is what Client.{c.method} would return.", *fdocs],
                        "        ",
                    )
                )
                if c.method == "broadcast":
                    p(f"        return self._add_broadcast({build})")
                else:
                    p(f"        return self._add({build}, {res})")
                continue
            doc = method_doc(c)
            if c.pro_only and not any("Centrifugo PRO only" in line for line in doc):
                doc.append("Centrifugo PRO only.")
            if c.method == "broadcast":
                doc += [
                    "",
                    "Channels succeed or fail on their own. It returns when every channel",
                    "got the publication. When Centrifugo carried the broadcast out and one",
                    "or more channels failed - up to all of them - it raises",
                    "BroadcastFailedChannelsError, whose ``result`` holds every channel's",
                    "outcome. Any other exception means it failed as a whole: no channel got",
                    "a reply. After a timeout or a network error Centrifugo may still have",
                    "published it. Retry it with broadcast_with_retry, which sends again only",
                    "the channels which may still succeed, with one idempotency_key.",
                ]
            extra = ["timeout: float | None = None"]
            call = f"self._invoke({build}, {res}, timeout)"
            tdoc = ["    timeout: Seconds bounding the call: request_timeout when None."]
            if c.method == "broadcast":
                call = f"self._broadcast({build}, timeout)"
            aw = "await " if kind == "async" else ""
            df = "async def" if kind == "async" else "def"
            p(f"    {df} {c.method}(" + ", ".join(["self", "*", *params, *extra]) + f") -> {res}:")
            out.extend(docstring([*doc, *fdocs, *tdoc] if fdocs else [*doc, "", "Args:", *tdoc], "        "))
            p(f"        return {aw}{call}")
            if c.method == "broadcast":
                p("")
                p(
                    f"    {df} broadcast_with_retry("
                    + ", ".join(
                        [
                            "self",
                            "*",
                            *params,
                            "max_attempts: int = 2",
                            "attempt_timeout: float | None = None",
                            "on_attempt_error: BroadcastAttemptCallback | None = None",
                            "timeout: float | None = None",
                        ]
                    )
                    + ") -> BroadcastResult:"
                )
                out.extend(
                    docstring(
                        [
                            "Broadcasts as broadcast does, and retries the channels which failed for",
                            "a temporary reason - see retryable - up to max_attempts (2 by default:",
                            "one retry).",
                            "",
                            "- Only the channels which may still succeed are sent again; when only",
                            "  channels which failed for good are left, it stops.",
                            "- Every attempt carries the same idempotency_key - made for the call",
                            "  when none is given - so that a channel which got the publication in",
                            "  an earlier attempt does not get it again. The memory, Redis and",
                            "  PostgreSQL brokers keep keys; the NATS broker ignores them, and a",
                            "  retry may publish again.",
                            "- The result holds every channel's last outcome, and the key: retrying",
                            "  later with it publishes only into the channels which did not get it.",
                            "",
                            "timeout, when set, bounds the whole call, waits included;",
                            "attempt_timeout - request_timeout by default - bounds each attempt.",
                            "on_attempt_error decides the wait between attempts, and may stop them:",
                            "see BroadcastAttemptCallback. It raises as broadcast does.",
                        ],
                        "        ",
                    )
                )
                p(
                    f"        return {aw}self._broadcast_with_retry({build}, max_attempts, attempt_timeout, on_attempt_error, timeout)"
                )
    p("")
    return "\n".join(out)


def format_code(code: str, path: Path) -> str:
    """code as ruff sorts its imports and formats it, so that the committed file
    passes the lint."""
    sort = subprocess.run(  # noqa: S603 - our own ruff, from the venv
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--select",
            "I",
            "--fix",
            "--quiet",
            "--stdin-filename",
            str(path),
            "-",
        ],
        input=code,
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
    )
    code = sort.stdout or code
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
        ("api.proto", ROOT / "cent" / "_commands.py", generate_commands),
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
