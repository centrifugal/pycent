"""The rules the client checks before sending: those which hold for every
Centrifugo. Everything else Centrifugo checks itself."""

from __future__ import annotations

from typing import Any

from cent._api import REQUESTS, BroadcastRequest, PublishRequest
from cent._errors import InvalidRequestError

# None means "not set": a payload which is JSON null goes as raw JSON (spec 3.4).
_NULL_HINT = " (to publish JSON null, pass data=cent.RawJSON('null'))"


def method_of(request: Any) -> str:
    """The API method of a request, or TypeError for anything else."""
    if type(request) not in REQUESTS:
        raise TypeError(f"{type(request).__name__} is not a request of the Centrifugo server API")
    method: str = request.api_method
    return method


def validate(request: Any) -> None:
    """InvalidRequestError for a request the client can tell is wrong."""
    if isinstance(request, PublishRequest):
        if not request.channel:
            raise InvalidRequestError("invalid publish request: channel is required")
        if request.data is None and not request.b64data:
            raise InvalidRequestError(f"invalid publish request: data or b64data is required{_NULL_HINT}")
    elif isinstance(request, BroadcastRequest):
        if not request.channels:
            raise InvalidRequestError("invalid broadcast request: channels is required")
        if request.data is None and not request.b64data:
            raise InvalidRequestError(f"invalid broadcast request: data or b64data is required{_NULL_HINT}")
        for i, ch in enumerate(request.channels):
            if not ch:
                raise InvalidRequestError(f"invalid broadcast request: channels[{i}] is empty")
