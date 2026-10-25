"""Broadcast results: one outcome per channel."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from cent import _wire as _w
from cent._api import PublishResult
from cent._errors import ApiError, BroadcastFailedChannelsError, DecodeError


@dataclass(slots=True, kw_only=True)
class ChannelResult:
    """The outcome of a broadcast in one channel."""

    channel: str
    """The channel, as the request named it."""

    result: PublishResult | None = None
    """The publication's position in the channel's history, when it succeeded."""

    error: Exception | None = None
    """None when the publication succeeded; the channel's ApiError, or the error
    of the whole broadcast when it failed as a whole."""

    attempts: int = 0
    """How many times the channel was sent: more than 1 when
    broadcast_with_retry retried it."""


@dataclass(slots=True, kw_only=True)
class BroadcastResult:
    """The outcome of a broadcast: one entry per channel, in the order the
    request listed them."""

    channels: list[ChannelResult] = field(default_factory=list)

    idempotency_key: str = ""
    """The key the broadcast was sent with: the request's, or the one
    broadcast_with_retry made when the request had none. A later retry with it
    does not publish again into the channels which got the publication."""

    attempts: int = 0
    """How many times the broadcast was tried: 1 from broadcast, up to
    max_attempts from broadcast_with_retry, 0 when it was refused before
    sending."""

    replied: bool = False
    """True when Centrifugo carried the broadcast out and replied for every
    channel, the failed ones included; False when it failed as a whole."""

    def failed(self) -> list[ChannelResult]:
        """The channels which did not get the publication, with their errors, in
        the order of the request."""
        return [ch for ch in self.channels if ch.error is not None]


def failed_as_whole(channels: list[str], err: Exception, attempts: int = 0) -> BroadcastResult:
    """The result of a broadcast which failed as a whole: every channel failed with err."""
    return BroadcastResult(
        channels=[ChannelResult(channel=ch, error=err, attempts=attempts) for ch in channels],
        attempts=attempts,
    )


def from_wire(v: Any, channels: list[str], key: str) -> BroadcastResult:
    """The result of a broadcast Centrifugo replied to, or BroadcastFailedChannelsError
    carrying it. The reply holds one response per channel, in the request's order."""
    d = _w.obj(v, "BroadcastResult")
    responses = d.get("responses") or []
    if not isinstance(responses, list):
        raise DecodeError("BroadcastResult.responses: expected an array")
    if len(responses) != len(channels):
        raise DecodeError(f"got {len(responses)} replies for {len(channels)} channels")
    res = BroadcastResult(idempotency_key=key, attempts=1, replied=True)
    for i, item in enumerate(responses):
        where = f"BroadcastResult.responses[{i}]"
        r = _w.obj(item, where)
        ch = ChannelResult(channel=channels[i], attempts=1)
        if (e := r.get("error")) is not None:
            ch.error = api_error(e, f"{where}.error")
        else:
            ch.result = PublishResult._from_wire(r.get("result") or {}, f"{where}.result")
        res.channels.append(ch)
    return res


def check(res: BroadcastResult) -> BroadcastResult:
    """res, or BroadcastFailedChannelsError carrying it when any channel failed."""
    failed = res.failed()
    if failed:
        raise BroadcastFailedChannelsError(failed, len(res.channels), res)
    return res


def api_error(v: Any, where: str) -> ApiError:
    """The ApiError of an error object in a reply."""
    d = _w.obj(v, where)
    return ApiError.from_wire(
        _w.scalar(d, "code", f"{where}.code", _w.c_int, 0),
        _w.scalar(d, "message", f"{where}.message", _w.c_str, ""),
        _w.scalar(d, "temporary", f"{where}.temporary", _w.c_bool, False),
    )
