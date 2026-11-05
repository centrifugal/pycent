"""The generator's reading of the protos' comments."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "gen"))

import generate  # noqa: E402

import proto  # noqa: E402


def _api() -> proto.Schema:
    return proto.parse((ROOT / "proto" / "api.proto").read_text(), "api.proto")


def test_presence_wrappers_and_unchecked_fields_from_comments() -> None:
    # Pinned, so that a changed comment shows as a failed test rather than as a
    # field changing how it is sent or checked (spec 2, 3.3).
    s = _api()
    wrappers = [m.name for m in s.messages if generate.is_presence(m)]
    assert wrappers == [
        "BoolValue",
        "Int32Value",
        "DeviceUserUpdate",
        "DeviceTimezoneUpdate",
        "DeviceLocaleUpdate",
        "DeviceMetaUpdate",
    ]
    unchecked = [
        f"{m.name}.{f.name}"
        for m in s.messages
        for f in m.fields
        if generate.required(f) and generate.empty_has_meaning(f)
    ]
    assert unchecked == [
        "InvalidateUserTokensRequest.user",
        "DeviceUserUpdate.user",
        "DeviceTimezoneUpdate.timezone",
        "DeviceLocaleUpdate.locale",
        "DeviceMetaUpdate.meta",
        "UserTopicUpdateRequest.user",
    ]


def test_proxy_has_no_presence_wrappers_but_its_own() -> None:
    s = proto.parse((ROOT / "proto" / "proxy.proto").read_text(), "proxy.proto")
    assert all(m.name in generate.WRAPPERS for m in s.messages if generate.is_presence(m))


def test_listed_values() -> None:
    assert generate.listed_values(["op is the operation. Required. One of: add, remove,", "set."]) == [
        "add",
        "remove",
        "set",
    ]
    assert generate.listed_values(["No list here."]) is None
    for doc, msg in [
        (["One of: add, remove"], "must end with a period"),
        (["One of: add, Remove."], "'Remove' is not a value"),
        (["One of: add, , set."], "'' is not a value"),
        (["One of: add, add."], "listed twice"),
    ]:
        with pytest.raises(generate.ConstError, match=msg):
            generate.listed_values(doc)


def _groups(text: str, pins: dict[str, str]) -> dict[str, str]:
    s = proto.parse(text, "test.proto")
    groups = generate.const_groups(s, {m.name for m in s.messages}, pins)
    return {g.name(v): v for g in groups for v in g.values}


_PROTO = """
message A {
  // One of: add, remove.
  string op = 1;
  // One of: if_new, if_exists.
  string key_mode = 2;
}
message B {
  // One of: add, remove.
  string op = 1;
}
message FilterNode {
  // One of: and, or.
  string op = 1;
}
"""


def test_constant_names_are_pinned() -> None:
    pins = {"A.op": "Op", "B.op": "Op", "*.key_mode": "KeyMode", "FilterNode.op": "FilterNodeOp"}
    assert _groups(_PROTO, pins) == {
        "OP_ADD": "add",
        "OP_REMOVE": "remove",
        "KEY_MODE_IF_NEW": "if_new",
        "KEY_MODE_IF_EXISTS": "if_exists",
        "FILTER_NODE_OP_AND": "and",
        "FILTER_NODE_OP_OR": "or",
    }


@pytest.mark.parametrize(
    ("pins", "msg"),
    [
        # A field with a "One of:" sentence the list lacks.
        ({"A.op": "Op", "*.key_mode": "KeyMode", "FilterNode.op": "FilterNodeOp"}, "B.op lists its values"),
        # A pin no field uses.
        (
            {"*.op": "Op", "*.key_mode": "KeyMode", "FilterNode.op": "FilterNodeOp", "Gone.f": "Gone"},
            "no field uses: Gone.f",
        ),
        # One name over different values.
        ({"*.op": "Op", "*.key_mode": "KeyMode"}, "Op names"),
    ],
)
def test_constant_pins_checked(pins: dict[str, str], msg: str) -> None:
    with pytest.raises(generate.ConstError, match=msg):
        _groups(_PROTO, pins)


def test_pins_of_the_protos() -> None:
    # The names spec 0.3 section 3.3 pins, in both protos alike.
    import cent
    from cent import proxy

    assert cent.FILTER_NODE_OP_AND == proxy.FILTER_NODE_OP_AND == "and"
    assert cent.CMP_EQ == proxy.CMP_EQ == "eq"
    assert cent.KEY_MODE_IF_NEW == proxy.KEY_MODE_IF_NEW == "if_new"
    assert (cent.PROVIDER_FCM, cent.PLATFORM_IOS, cent.OP_ADD, cent.STATUS_DELIVERED) == (
        "fcm",
        "ios",
        "add",
        "delivered",
    )
    assert (proxy.PROTOCOL_PROTOBUF, proxy.ENCODING_BINARY, proxy.ALLOW_SUB) == ("protobuf", "binary", "sub")
    assert (proxy.CAPABILITY_MATCH_WILDCARD, proxy.CHANNEL_EVENT_TYPE_OCCUPIED) == ("wildcard", "occupied")
    for gone in ("OP_AND", "MATCH_WILDCARD", "TYPE_OCCUPIED"):
        assert not hasattr(proxy, gone)
    # Each pinned list as the generator reads it: every line used.
    for path in ("constants_api.txt", "constants_proxy.txt"):
        assert generate.read_pins(ROOT / "gen" / path)


def test_each_constant_equals_its_value() -> None:
    import cent
    from cent import proxy

    for module, path in ((cent, "api.proto"), (proxy, "proxy.proto")):
        s = proto.parse((ROOT / "proto" / path).read_text(), path)
        listed = {
            v for m in s.messages for f in m.fields if (vs := generate.listed_values(f.doc)) is not None for v in vs
        }
        consts = {n: getattr(module, n) for n in module.__all__ if n.isupper() and isinstance(getattr(module, n), str)}
        consts.pop("DEFAULT_MAX_BODY", None)
        for name, value in consts.items():
            assert name.endswith("_" + value.upper()), name
        assert set(consts.values()) == listed, path
