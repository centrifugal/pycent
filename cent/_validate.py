"""The rules the client checks before sending: those which hold for every
Centrifugo - the protos' "Required." marks, generated as each request's
_required, and the data rules. Everything else Centrifugo checks itself."""

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
    """InvalidRequestError for a request the client can tell is wrong: a field
    the proto marks "Required." without a value - unset, or given empty, which
    is not sent - named by its path, such as
    limit_strategy.rate_limit.policies[0].rate; and the data rules of publish
    and broadcast (spec 3.5). A required field whose empty value has a
    meaning - invalidate_user_tokens' user, say - is not checked."""
    if path := request._required():
        raise InvalidRequestError(f"invalid {request.api_method} request: {path} is required")
    if isinstance(request, PublishRequest):
        if request.data is None and not request.b64data:
            raise InvalidRequestError(f"invalid publish request: data or b64data is required{_NULL_HINT}")
    elif isinstance(request, BroadcastRequest):
        if request.data is None and not request.b64data:
            raise InvalidRequestError(f"invalid broadcast request: data or b64data is required{_NULL_HINT}")
        for i, ch in enumerate(request.channels):
            if not ch:
                raise InvalidRequestError(f"invalid broadcast request: channels[{i}] is empty")
