"""Payloads: the JSON values of data, info, meta and the like."""

from __future__ import annotations

import json
import math
from typing import Any, NoReturn

from cent._errors import InvalidRequestError

JSON = Any
"""A payload: a JSON value given as the Python value it decodes to - a dict,
list, str, int, float, bool or None - or RawJSON. A str is a JSON string,
never raw JSON."""


def _reject_constant(name: str) -> NoReturn:
    raise ValueError(f"{name} is not a JSON number")


class RawJSON:
    """JSON text, sent as it is: a payload already encoded - from a database,
    a queue, a cache - or encoded with rules of your own (a faster encoder,
    dates, decimals). It is checked to be valid JSON when created, and sent
    unchanged, number text kept.

    >>> cent.PublishRequest(channel="news", data=cent.RawJSON('{"text":"hi"}'))
    """

    __slots__ = ("_text",)

    def __init__(self, text: str | bytes) -> None:
        if isinstance(text, bytes):
            try:
                text = text.decode("utf-8")
            except UnicodeDecodeError as e:
                raise InvalidRequestError(f"raw JSON is not valid UTF-8: {e}") from e
        if not isinstance(text, str):
            raise TypeError(f"RawJSON takes str or bytes, not {type(text).__name__}")
        try:
            # NaN and infinities, which Python's json accepts, are not JSON.
            json.loads(text, parse_constant=_reject_constant)
        except ValueError as e:
            raise InvalidRequestError(f"raw JSON is not valid JSON: {e}") from e
        self._text = text

    @property
    def text(self) -> str:
        """The JSON text."""
        return self._text

    def __repr__(self) -> str:
        return f"RawJSON({self._text!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, RawJSON) and other._text == self._text

    def __hash__(self) -> int:
        return hash(self._text)


def _payload_default(o: object) -> NoReturn:
    if isinstance(o, (bytes, bytearray, memoryview)):
        raise TypeError("bytes are not JSON: send binary base64-encoded in a b64 field, such as b64data")
    if isinstance(o, RawJSON):
        raise TypeError("RawJSON inside a value: pass it as the whole payload, or decode it")
    raise TypeError(f"{type(o).__name__} is not a JSON value")


def encode_payload(value: JSON, where: str) -> str:
    """value as JSON text, or InvalidRequestError naming where it is."""
    if isinstance(value, RawJSON):
        return value.text
    if isinstance(value, float) and not math.isfinite(value):
        raise InvalidRequestError(f"{where} is {value}, which is not a JSON number")
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"), default=_payload_default)
    except (TypeError, ValueError, RecursionError) as e:
        raise InvalidRequestError(f"{where} cannot be encoded: {e}") from e
