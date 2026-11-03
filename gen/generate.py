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
from dataclasses import dataclass
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


# The paged methods (spec 3.8): the result field holding a page's items, and
# the one holding the next page's cursor - None for history, paged by since -
# and the docs of their <method>_all iterators.
PAGED: dict[str, tuple[str, str | None, list[str]]] = {
    "history": (
        "publications",
        None,
        [
            "The publications of a channel's history, oldest first, a page of limit",
            "at a time: from since when it is set, from the start of what the channel",
            "keeps otherwise. A page is read when the iteration reaches it, and the",
            "iteration ends after a page shorter than limit::",
            "",
            '    for pub in client.history_all(channel="news", limit=100):',
            "        handle(pub)",
            "",
            "limit is the page size, so it must be 1 or more, and reverse is refused:",
            "since reads forward only. Both raise InvalidRequestError at the call,",
            "before anything is sent. A publication made while iterating may or may",
            "not be seen. An epoch which changed since a page was read - the history",
            "was lost, with a Redis restart say - raises UnrecoverablePositionError:",
            "the publications after the last one seen are gone, and reading again",
            "from the start is the only way on.",
        ],
    ),
    "device_list": (
        "items",
        "next_cursor",
        [
            "Every device the request selects, a page at a time, each page read when",
            "the iteration reaches it: limit is the page size, the server's default",
            "when unset. A device registered or removed while iterating may or may",
            "not be seen.",
        ],
    ),
    "device_topic_list": (
        "items",
        "next_cursor",
        [
            "Every device topic the request selects, a page at a time, as",
            "device_list_all reads devices. A topic added or removed while iterating",
            "may or may not be seen.",
        ],
    ),
    "user_topic_list": (
        "items",
        "next_cursor",
        [
            "Every user topic the request selects, a page at a time, as",
            "device_list_all reads devices. A topic added or removed while iterating",
            "may or may not be seen.",
        ],
    ),
    "map_read_state": (
        "entries",
        "cursor",
        [
            "Every entry of a map channel's state, a page at a time, each page read",
            "when the iteration reaches it: limit is the page size. Every page after",
            "the first is read at the first one's revision - its position(), as",
            "revision_offset and revision_epoch, unless the call sets them - so that",
            "a state reset between pages raises UnrecoverablePositionError instead",
            "of mixing two states: read again from the start then. Entries changed",
            "while iterating may be seen in either version; for a consistent view,",
            "read the changes since the first page's position with map_read_stream.",
        ],
    ),
}

# The results holding a stream position as offset and epoch (spec 3.8), and
# the docs of their position().
POSITIONS: dict[str, list[str]] = {
    "PublishResult": [
        "Where the publication went in the channel's stream: the since of a",
        "history call reading what came after it.",
    ],
    "HistoryResult": ["The channel's stream position when the history was read."],
    "MapReadStateResult": [
        "The map channel's stream position when its state was read: as",
        "map_read_stream's since_offset and since_epoch, it reads the changes since.",
    ],
    "MapReadStreamResult": ["The map channel's stream position when its stream was read."],
    "MapPublishResult": [
        "Where the publication went in the map channel's stream: as",
        "map_read_stream's since_offset and since_epoch, it reads what came after it.",
    ],
    "MapRemoveResult": [
        "Where the removal went in the map channel's stream: as",
        "map_read_stream's since_offset and since_epoch, it reads what came after it.",
    ],
}


def positions(s: Schema) -> set[str]:
    """The results holding offset and epoch, which give them as position()
    (spec 3.8): found by the two fields, each needing its docs in POSITIONS."""
    results = {f.type for f in s.by_name["Reply"].fields}
    found = set()
    for name in results:
        m = s.by_name[name]
        types = {f.name: f.type for f in m.fields}
        if types.get("offset") == "uint64" and types.get("epoch") == "string":
            found.add(name)
    if found != set(POSITIONS):
        raise SystemExit(f"api.proto: the results holding offset and epoch are {sorted(found)}: update POSITIONS")
    return found


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


def empty_has_meaning(f: Field) -> bool:
    """Whether a field's comment gives its empty value a meaning after
    "Required." - `"" detaches the devices`, `An empty map clears it.` (spec
    3.3). Such a field is required in the signature but not checked before
    sending, since a check could not tell empty from missing."""
    _, sep, after = " ".join(f.doc).partition("Required.")
    return bool(sep) and ('""' in after or "empty" in after.lower())


def is_presence(m: Message | None) -> bool:
    """Whether a message is a presence wrapper (spec 2): one field, which
    Centrifugo reads by whether the message is there - a *Value message whose
    field is value, or one whose only field gives its empty value a meaning,
    as device_update's user_update. Sent whenever set, even empty."""
    if m is None or len(m.fields) != 1:
        return False
    if m.name.endswith("Value") and m.fields[0].name == "value":
        return True
    return empty_has_meaning(m.fields[0])


# The presence wrappers of the proto being generated, but those of WRAPPERS,
# which become optional scalars: set by find_presence.
PRESENCE: set[str] = set()


def find_presence(s: Schema, name: str) -> None:
    """Records the presence wrappers of s in PRESENCE. A *Value wrapper must be
    one of WRAPPERS, which say its Python type."""
    PRESENCE.clear()
    SCHEMA.clear()
    SCHEMA.update(s.by_name)
    _NEEDS.clear()
    for m in s.messages:
        if not is_presence(m):
            continue
        if m.name.endswith("Value") and m.fields[0].name == "value":
            if m.name not in WRAPPERS:
                raise SystemExit(f"{name}: {m.name} is a presence wrapper gen/generate.py has no Python type for")
            continue
        PRESENCE.add(m.name)


_VALUE = re.compile(r"^[a-z][a-z0-9_]*$")


class ConstError(Exception):
    pass


def listed_values(doc: list[str]) -> list[str] | None:
    """The values a field's comment lists in the sentence "One of: add, remove,
    set.", or None without one (spec 3.3). A malformed sentence fails, rather
    than being skipped."""
    _, sep, after = " ".join(doc).partition("One of:")
    if not sep:
        return None
    listed, period, _ = after.partition(".")
    if not period:
        raise ConstError('the values after "One of:" must end with a period')
    values: list[str] = []
    for raw in listed.split(","):
        v = raw.strip()
        if not _VALUE.match(v):
            raise ConstError(f"{v!r} is not a value: lowercase letters, digits and underscores")
        if v in values:
            raise ConstError(f"value {v!r} listed twice")
        values.append(v)
    return values


def snake(name: str) -> str:
    """FilterNode -> filter_node."""
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", "_", name).lower()


@dataclass
class ConstGroup:
    """The constants of a string field with listed values: the values, and the
    messages whose field of that name lists exactly them."""

    field: str
    values: list[str]
    messages: list[str]
    prefix: str = ""  # the message, when the field name alone is ambiguous

    def name(self, value: str) -> str:
        """PROVIDER_FCM for the provider field's "fcm"."""
        prefix = snake(self.prefix) + "_" if self.prefix else ""
        return f"{prefix}{self.field}_{value}".upper()


def const_groups(s: Schema, include: set[str]) -> list[ConstGroup]:
    """The fields of the messages in include which list their values, grouped,
    in the order of the proto. A constant is named by its field and value;
    where fields of one name list different values in different messages, the
    set listed in the most messages keeps the short name and the others are
    named by their message too - OP_ADD for the topic updates, FILTER_NODE_OP_AND
    for FilterNode - and a tie names all of them so (spec 3.3)."""
    by_field: dict[str, list[ConstGroup]] = {}
    for m in s.messages:
        if m.name not in include:
            continue
        for f in m.fields:
            try:
                values = listed_values(f.doc)
            except ConstError as e:
                raise ConstError(f"{m.name}.{f.name}: {e}") from None
            if values is None:
                continue
            groups = by_field.setdefault(f.name, [])
            for g in groups:
                if g.values == values:
                    g.messages.append(m.name)
                    break
            else:
                groups.append(ConstGroup(f.name, values, [m.name]))
    out: list[ConstGroup] = []
    for name, groups in by_field.items():
        if len(groups) > 1:
            most = max(len(g.messages) for g in groups)
            tie = sum(len(g.messages) == most for g in groups) > 1
            for g in groups:
                if tie or len(g.messages) < most:
                    if len(g.messages) > 1:
                        raise ConstError(
                            f"field {name} lists {g.values} in {g.messages} and other values elsewhere:"
                            " cannot name its constants"
                        )
                    g.prefix = g.messages[0]
        out.extend(groups)
    names: dict[str, str] = {}
    for g in out:
        for v in g.values:
            n = g.name(v)
            if n in names:
                raise ConstError(f"constant {n} names {v!r} of {g.messages} and {names[n]}")
            names[n] = f"{g.messages}"
    return out


def emit_consts(out: list[str], groups: list[ConstGroup], methods: dict[str, str] | None = None) -> None:
    """A constant per listed value, each with a docstring naming its field: a
    request's by its method, whose argument it is."""
    for g in groups:
        where = [f"{methods[m]}" if methods and m in methods else m for m in g.messages]
        fields = f"the {g.field} field of " + (
            ", ".join(where[:-1]) + " and " + where[-1] if len(where) > 1 else where[0]
        )
        out.append("")
        for v in g.values:
            out.append(f"{g.name(v)}: Final = {v!r}")
            out.extend(docstring(textwrap.wrap(f"A value of {fields}.", 76), ""))


def const_names(groups: list[ConstGroup]) -> list[str]:
    return [g.name(v) for g in groups for v in g.values]


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
    if t in PRESENCE:
        # A presence wrapper: sent whenever set, even empty - an empty user
        # update detaches the devices, an absent one changes nothing.
        return [f"if {n} is not None:", f"    w[{key}] = {n}._to_wire()"]
    # A nested message, left out when nothing in it is set: Centrifugo reads
    # some by whether they are there, and refuses an empty limit_strategy.
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


# The messages of the proto being generated, for the required-field checks:
# set by find_presence.
SCHEMA: dict[str, Message] = {}
_NEEDS: dict[str, bool] = {}


def is_message(f: Field) -> bool:
    return f.type in SCHEMA and f.type not in WRAPPERS


def checked(f: Field) -> bool:
    """Whether the client checks before sending that f has a value: a field
    the proto marks "Required." whose empty value has no meaning (spec 3.3,
    3.5)."""
    return required(f) and not empty_has_meaning(f)


def needs_check(name: str) -> bool:
    """Whether a message has fields to check, itself or in a message it
    holds. A presence wrapper has none: its field may be empty."""
    if name in _NEEDS:
        return _NEEDS[name]
    _NEEDS[name] = False  # a message holding itself adds nothing
    m = SCHEMA[name]
    v = any(checked(f) or (is_message(f) and f.type not in PRESENCE and needs_check(f.type)) for f in m.fields)
    _NEEDS[name] = v
    return v


def emit_required(out: list[str], m: Message) -> None:
    """The _required method of a message: the path of a field the proto marks
    "Required." which it leaves without a value, or "" - nested messages
    checked when set, a required one when unset too, list elements each."""
    p = out.append
    p("")
    p("    def _required(self) -> str:")
    body: list[str] = []
    for f in m.fields:
        n, name = f"self.{f.name}", f.name
        if checked(f):
            if f.type == "bool" and not f.repeated and not f.map_key:
                raise SystemExit(
                    f"api.proto: {m.name}.{f.name}: a bool cannot be required: false and unset are one value"
                )
            if f.repeated or f.map_key or f.type in PY_TYPES:
                cond = f"not {n}"
            elif f.type == "bytes":
                cond = f"{n} is None"
            else:
                cond = f"not _w.is_set({n})"
            body += [f"if {cond}:", f"    return {name!r}"]
        if not is_message(f) or f.type in PRESENCE or not needs_check(f.type):
            continue
        if f.map_key:
            raise SystemExit(f"api.proto: {m.name}.{f.name}: a map of messages with required fields is not supported")
        if f.repeated:
            body += [
                f"for i, v in enumerate({n}):",
                "    if p := v._required():",
                f"        return f'{name}[{{i}}].{{p}}'",
            ]
        else:
            body += [
                f"if {n} is not None and _w.is_set({n}) and (p := {n}._required()):",
                f"    return {name + '.'!r} + p",
            ]
    out.extend("        " + line for line in [*body, "return ''"])


# The fields made required arguments, as "Message.field": checked against
# REQUIRED_FILE, so that a proto comment gaining "Required." - a breaking
# change of the methods taking it - is a decision, not a side effect of a sync.
REQUIRED: set[str] = set()
REQUIRED_FILE = ROOT / "gen" / "required_fields.txt"


def check_required(accept: bool) -> None:
    """Fails when the required fields differ from REQUIRED_FILE; with accept,
    records them there instead."""
    want = sorted(REQUIRED)
    if accept:
        REQUIRED_FILE.write_text("".join(f"{r}\n" for r in want))
        return
    have = REQUIRED_FILE.read_text().split() if REQUIRED_FILE.exists() else []
    added, removed = sorted(set(want) - set(have)), sorted(set(have) - set(want))
    if added or removed:
        raise SystemExit(
            "the fields the protos mark Required. changed:"
            + (f"\n  newly required (breaking: calls without them fail): {', '.join(added)}" if added else "")
            + (f"\n  no longer required: {', '.join(removed)}" if removed else "")
            + "\nReview them, then run gen/generate.py --accept-required to record them in gen/required_fields.txt"
        )


def kwargs(m: Message) -> tuple[list[str], list[str]]:
    """The keyword parameters of a request's method, and the arguments building
    the request from them. Lists and maps default to None, made empty."""
    params, args = [], []
    for f in m.fields:
        if keyword.iskeyword(f.name):
            raise SystemExit(f"api.proto: {m.name}.{f.name} is a Python keyword: no keyword argument can carry it")
        ann, default = field_type(f)
        if required(f):
            REQUIRED.add(f"{m.name}.{f.name}")
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
        if required(f) and not is_message(f):
            # A field the proto marks "Required." is a required argument of
            # the dataclass too: DeviceTopicsUpdate(op=...).
            if protocol == "server API":
                REQUIRED.add(f"{m.name}.{f.name}")
            p(f"    {f.name}: {ann}")
        else:
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
    if protocol == "server API" and (api_method is not None or needs_check(m.name)):
        emit_required(out, m)
    if protocol == "server API" and m.name in POSITIONS:
        names = {f.name: f.type for f in m.fields}
        if names.get("offset") != "uint64" or names.get("epoch") != "string":
            raise SystemExit(f"api.proto: {m.name} has no offset and epoch for its position()")
        p("")
        p("    def position(self) -> StreamPosition:")
        out.extend(docstring(POSITIONS[m.name], "        "))
        p("        return StreamPosition(offset=self.offset, epoch=self.epoch)")
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
    find_presence(s, "api.proto")
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
    find_presence(s, "proxy.proto")
    msgs = proxy_messages(s)
    out: list[str] = []
    p = out.append
    p("# Code generated by gen/generate.py from proto/proxy.proto. DO NOT EDIT.")
    p('"""The requests and results of the Centrifugo proxy protocol."""')
    p("")
    p("from __future__ import annotations")
    p("")
    p("from dataclasses import dataclass, field")
    p("from typing import Any, Final")
    p("")
    p("from cent import _wire as _w")
    p("from cent._payload import JSON")
    groups = const_groups(s, {m.name for m in msgs})
    p("")
    p("__all__ = [")
    for name in sorted(const_names(groups)) + sorted(m.name for m in msgs):
        p(f"    {name!r},")
    p("]")
    p("")
    p("# The values of the string fields with a fixed set, from the proto's")
    p('# "One of:" sentences: what a handler compares a request\'s fields with, or')
    p("# sets in a result. The fields are strings: a value Centrifugo sends or")
    p("# accepts which these do not name is still a valid one.")
    emit_consts(out, groups)
    for m in msgs:
        emit_message(out, m, None, "proxy protocol")
    p("")
    return "\n".join(out)


def generate(s: Schema) -> str:
    find_presence(s, "api.proto")
    positions(s)
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
    p("from typing import TYPE_CHECKING, Any, ClassVar, Final, TypeVar")

    p("")
    p("from cent import _wire as _w")
    p("from cent._payload import JSON")
    p("")
    p("if TYPE_CHECKING:")
    p("    from collections.abc import AsyncIterator, Iterator")
    p("")
    p("    from cent._batch import Pending")
    p("    from cent._broadcast import BroadcastResult")
    p("    from cent._client import BroadcastAttemptCallback")
    p("")
    p('_R = TypeVar("_R")')
    # The requests are the methods' keyword arguments: their dataclasses are
    # internal. Nested messages and results are public.
    request_names = {c.request.name for c in cmds}
    public = [m.name for m in s.messages if m.name not in skip and m.name not in request_names]
    groups = const_groups(s, {m.name for m in s.messages if m.name not in skip})
    p("")
    p("__all__ = [")
    for name in sorted(const_names(groups)) + sorted(public):
        p(f"    {name!r},")
    p("]")
    p("")
    p("# The values of the string fields with a fixed set, from the proto's")
    p('# "One of:" sentences. The fields are strings: a value Centrifugo accepts')
    p("# which these do not name can still be sent.")
    emit_consts(out, groups, {c.request.name: c.method for c in cmds})

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
            p("        def _history_all(self, request: HistoryRequest, timeout: float | None) -> Iterator[Any]: ...")
            p("        def _cursor_all(")
            p("            self, request: Any, result: type[Any], items: str, cursor: str, timeout: float | None")
            p("        ) -> Iterator[Any]: ...")
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
                "        def _history_all(self, request: HistoryRequest, timeout: float | None) -> AsyncIterator[Any]: ..."
            )
            p("        def _cursor_all(")
            p("            self, request: Any, result: type[Any], items: str, cursor: str, timeout: float | None")
            p("        ) -> AsyncIterator[Any]: ...")
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
            if c.method in PAGED:
                items, cursor, pdoc = PAGED[c.method]
                rmsg = s.by_name[c.result]
                (item_field,) = [f for f in rmsg.fields if f.name == items and f.repeated]
                if cursor is not None and not any(f.name == cursor for f in rmsg.fields):
                    raise SystemExit(f"api.proto: {c.result} has no {cursor}")
                it = "AsyncIterator" if kind == "async" else "Iterator"
                doc = list(pdoc)
                if kind == "async":
                    doc = [line.replace("    for pub in client.", "    async for pub in client.") for line in doc]
                if c.pro_only:
                    doc.append("Centrifugo PRO only.")
                p("")
                p(
                    f"    def {c.method}_all("
                    + ", ".join(["self", "*", *params, *extra])
                    + f") -> {it}[{item_field.type}]:"
                )
                tdoc_all = ["    timeout: Seconds bounding each page's call: request_timeout when None."]
                out.extend(docstring([*doc, *fdocs, *tdoc_all], "        "))
                if cursor is None:
                    p(f"        return self._history_all({build}, timeout)")
                else:
                    p(f"        return self._cursor_all({build}, {c.result}, {items!r}, {cursor!r}, timeout)")
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
    ap.add_argument(
        "--accept-required", action="store_true", help="record the fields the protos mark Required. as reviewed"
    )
    args = ap.parse_args()
    outputs = [
        ("api.proto", ROOT / "cent" / "_api.py", generate),
        ("api.proto", ROOT / "cent" / "_commands.py", generate_commands),
        ("proxy.proto", ROOT / "cent" / "proxy" / "_types.py", generate_proxy),
    ]
    codes = []
    for proto_name, out_path, gen in outputs:
        src_path = ROOT / "proto" / proto_name
        try:
            code = gen(parse(src_path.read_text(), src_path.name))
        except ConstError as e:
            raise SystemExit(f"{proto_name}: {e}") from None
        codes.append((out_path, format_code(code, out_path)))
    # Before writing: nothing is generated from unreviewed required fields.
    check_required(args.accept_required)
    stale = []
    for out_path, code in codes:
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
