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


def _groups(text: str) -> dict[str, str]:
    s = proto.parse(text, "test.proto")
    groups = generate.const_groups(s, {m.name for m in s.messages})
    return {g.name(v): v for g in groups for v in g.values}


def test_constant_names() -> None:
    # The set listed in the most messages keeps the short name; the others are
    # named by their message too.
    consts = _groups(
        """
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
    )
    assert consts == {
        "OP_ADD": "add",
        "OP_REMOVE": "remove",
        "KEY_MODE_IF_NEW": "if_new",
        "KEY_MODE_IF_EXISTS": "if_exists",
        "FILTER_NODE_OP_AND": "and",
        "FILTER_NODE_OP_OR": "or",
    }


def test_constant_names_tie() -> None:
    # A tie names every set by its message.
    consts = _groups(
        """
message A {
  // One of: x, y.
  string kind = 1;
}
message B {
  // One of: z.
  string kind = 1;
}
"""
    )
    assert consts == {"A_KIND_X": "x", "A_KIND_Y": "y", "B_KIND_Z": "z"}


def test_constants_per_proto() -> None:
    # The rule runs over each proto on its own: FilterNode.op is the API's
    # FILTER_NODE_OP_AND, the proxy's OP_AND.
    import cent
    from cent import proxy

    assert cent.FILTER_NODE_OP_AND == proxy.OP_AND == "and"
    assert not hasattr(proxy, "FILTER_NODE_OP_AND")
    assert not hasattr(cent, "OP_AND")


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
