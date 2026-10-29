"""A parser for the part of proto3 Centrifugo's api.proto and proxy.proto use.

Top-level messages with scalar, message, repeated and map fields, and one
service whose methods may stream. Anything else - a oneof, an enum, a nested
message - fails the generation, rather than being dropped from the SDK
without a word.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

SCALARS = {"string", "bool", "int32", "int64", "uint32", "uint64", "double", "float", "bytes"}

_MESSAGE_OPEN = re.compile(r"^message\s+(\w+)\s*\{\s*(\})?$")
_FIELD = re.compile(r"^(repeated\s+)?(\w+)\s+(\w+)\s*=\s*\d+\s*;$")
_MAP_FIELD = re.compile(r"^map\s*<\s*(\w+)\s*,\s*(\w+)\s*>\s+(\w+)\s*=\s*\d+\s*;$")
_RESERVED = re.compile(r"^reserved\s+[\d\s,to]+;$")
_SERVICE_OPEN = re.compile(r"^service\s+\w+\s*\{$")
_RPC = re.compile(
    r"^rpc\s+(\w+)\s*\(\s*(stream\s+)?(\w+)\s*\)\s*returns\s*\(\s*(stream\s+)?(\w+)\s*\)\s*(?:\{\s*\}|;)$"
)
_TOP_LEVEL_SKIP = re.compile(r"^(syntax|package|option)\b.*;$")


@dataclass
class Field:
    name: str
    type: str  # scalar or message type; the value type for maps
    repeated: bool = False
    map_key: str = ""
    doc: list[str] = field(default_factory=list)


@dataclass
class Message:
    name: str
    doc: list[str]
    fields: list[Field] = field(default_factory=list)


@dataclass
class Method:
    name: str
    request: str
    response: str
    streaming: bool


@dataclass
class Schema:
    messages: list[Message] = field(default_factory=list)
    by_name: dict[str, Message] = field(default_factory=dict)
    methods: list[Method] = field(default_factory=list)


class ProtoError(Exception):
    pass


def parse(text: str, name: str) -> Schema:
    s = Schema()
    comment: list[str] = []
    current: Message | None = None
    in_service = False
    line_no = 0

    def fail(msg: str) -> ProtoError:
        return ProtoError(f"{name}:{line_no}: {msg}")

    for line_no, raw in enumerate(text.splitlines(), 1):  # noqa: B007 - read by fail
        line = raw.strip()
        if line == "":
            # A blank line ends a comment block: only a comment directly
            # above a declaration documents it.
            comment = []
            continue
        if line.startswith("//"):
            comment.append(line[2:].strip())
            continue
        if "//" in line:
            # A trailing comment documents its line when nothing above does.
            i = line.index("//")
            if not comment:
                comment = [line[i + 2 :].strip()]
            line = line[:i].strip()

        if current is None and not in_service:
            if _TOP_LEVEL_SKIP.match(line):
                pass
            elif m := _MESSAGE_OPEN.match(line):
                if m[1] in s.by_name:
                    raise fail(f"message {m[1]} declared twice")
                msg = Message(name=m[1], doc=comment)
                s.messages.append(msg)
                s.by_name[msg.name] = msg
                if not m[2]:
                    current = msg
            elif _SERVICE_OPEN.match(line):
                in_service = True
            else:
                raise fail(f"unsupported top-level declaration: {line!r}")
        elif in_service:
            if line == "}":
                in_service = False
            elif m := _RPC.match(line):
                s.methods.append(Method(m[1], m[3], m[5], bool(m[2] or m[4])))
            else:
                raise fail(f"unsupported service declaration: {line!r}")
        else:
            assert current is not None
            if line == "}":
                current = None
            elif _RESERVED.match(line):
                pass
            elif m := _MAP_FIELD.match(line):
                current.fields.append(Field(name=m[3], type=m[2], map_key=m[1], doc=comment))
            elif m := _FIELD.match(line):
                current.fields.append(Field(name=m[3], type=m[2], repeated=bool(m[1]), doc=comment))
            else:
                raise fail(f"unsupported declaration in message {current.name}: {line!r}")
        comment = []
    if current is not None or in_service:
        raise ProtoError(f"{name}: unexpected end of file")
    _check(s, name)
    return s


def _check(s: Schema, name: str) -> None:
    """Every type a field or method refers to is declared."""
    for m in s.messages:
        for f in m.fields:
            if f.type not in SCALARS and f.type not in s.by_name:
                raise ProtoError(f"{name}: {m.name}.{f.name} has unknown type {f.type}")
            if f.map_key and f.map_key != "string":
                raise ProtoError(f"{name}: {m.name}.{f.name}: only string map keys are supported")
    for rpc in s.methods:
        if rpc.request not in s.by_name or rpc.response not in s.by_name:
            raise ProtoError(f"{name}: rpc {rpc.name} refers to an undeclared message")
