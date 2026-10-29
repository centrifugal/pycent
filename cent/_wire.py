"""Encoding requests and decoding replies, for the generated types."""

from __future__ import annotations

import json
import secrets
from collections.abc import Callable
from typing import Any, TypeVar

from cent._errors import DecodeError, InvalidRequestError
from cent._payload import JSON, encode_payload

_T = TypeVar("_T")


class _Payload:
    """A payload in a request being encoded: encoded on its own, then spliced
    into the request's JSON as it is."""

    __slots__ = ("value", "where")

    def __init__(self, value: JSON, where: str) -> None:
        self.value = value
        self.where = where


def payload(value: JSON, where: str) -> _Payload:
    return _Payload(value, where)


def encode(wire: dict[str, Any], method: str) -> bytes:
    """The JSON body of a request, from its _to_wire form.

    Payloads are encoded apart - raw JSON as it is, native values with
    NaN, infinities and bytes refused - and replace placeholders in the
    encoded request. The placeholders carry a random nonce, so that no string
    of the request - a channel name, say - can pass for one.
    """
    encoded: list[str] = []
    nonce = secrets.token_hex(8)

    def default(o: object) -> str:
        if isinstance(o, _Payload):
            try:
                encoded.append(encode_payload(o.value, o.where))
            except InvalidRequestError as e:
                raise InvalidRequestError(f"invalid {method} request: {e}") from e.__cause__
            return f"\x00{nonce}{len(encoded) - 1}\x00"
        raise TypeError(f"{type(o).__name__} is not a JSON value")

    try:
        text = json.dumps(wire, ensure_ascii=False, allow_nan=False, separators=(",", ":"), default=default)
    except InvalidRequestError:
        raise
    except (TypeError, ValueError, RecursionError) as e:
        raise InvalidRequestError(f"invalid {method} request: cannot be encoded: {e}") from e
    for i, text_i in enumerate(encoded):
        placeholder = json.dumps(f"\x00{nonce}{i}\x00", ensure_ascii=False)
        text = text.replace(placeholder, text_i, 1)
    try:
        return text.encode("utf-8")
    except UnicodeEncodeError as e:
        raise InvalidRequestError(f"invalid {method} request: a string is not valid UTF-8: {e}") from e


# Decoding: each helper takes the decoded JSON and the name of what it decodes,
# for the DecodeError of a reply not of the expected shape. Fields left out of
# a reply take their zero value; fields the client does not know are ignored.


def obj(v: Any, where: str) -> dict[str, Any]:
    if not isinstance(v, dict):
        raise DecodeError(f"{where}: expected an object, got {_kind(v)}")
    return v


def c_str(v: Any, where: str) -> str:
    if not isinstance(v, str):
        raise DecodeError(f"{where}: expected a string, got {_kind(v)}")
    return v


def c_bool(v: Any, where: str) -> bool:
    if not isinstance(v, bool):
        raise DecodeError(f"{where}: expected a boolean, got {_kind(v)}")
    return v


def c_int(v: Any, where: str) -> int:
    if not isinstance(v, int) or isinstance(v, bool):
        raise DecodeError(f"{where}: expected an integer, got {_kind(v)}")
    return v


def c_float(v: Any, where: str) -> float:
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        raise DecodeError(f"{where}: expected a number, got {_kind(v)}")
    return float(v)


def c_json(v: Any, where: str) -> JSON:
    return v


def scalar(d: dict[str, Any], key: str, where: str, conv: Callable[[Any, str], _T], zero: _T) -> _T:
    v = d.get(key)
    if v is None:
        return zero
    return conv(v, where)


def message(d: dict[str, Any], key: str, where: str, conv: Callable[[Any, str], _T]) -> _T | None:
    v = d.get(key)
    if v is None:
        return None
    return conv(v, where)


def wrapper(d: dict[str, Any], key: str, where: str, conv: Callable[[Any, str], _T]) -> _T | None:
    """A BoolValue or Int32Value: None when absent, its value otherwise."""
    v = d.get(key)
    if v is None:
        return None
    w = obj(v, where)
    inner = w.get("value")
    if inner is None:
        # The value's zero, which a protobuf encoder leaves out.
        return conv(False if conv is c_bool else 0, where)
    return conv(inner, where)


def list_of(d: dict[str, Any], key: str, where: str, conv: Callable[[Any, str], _T]) -> list[_T]:
    v = d.get(key)
    if v is None:
        return []
    if not isinstance(v, list):
        raise DecodeError(f"{where}: expected an array, got {_kind(v)}")
    return [conv(item, f"{where}[{i}]") for i, item in enumerate(v)]


def dict_of(d: dict[str, Any], key: str, where: str, conv: Callable[[Any, str], _T]) -> dict[str, _T]:
    v = d.get(key)
    if v is None:
        return {}
    m = obj(v, where)
    return {k: conv(item, f"{where}[{k!r}]") for k, item in m.items()}


def _kind(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "a boolean"
    if isinstance(v, (int, float)):
        return "a number"
    if isinstance(v, str):
        return "a string"
    if isinstance(v, list):
        return "an array"
    if isinstance(v, dict):
        return "an object"
    return type(v).__name__
