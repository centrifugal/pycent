"""The generator's reading of the protos' comments."""

from __future__ import annotations

import sys
from pathlib import Path

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
