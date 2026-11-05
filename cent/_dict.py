"""Results as JSON-ready data: for a frontend, a log, a queue."""

from __future__ import annotations

import dataclasses
import json
from typing import Any

from cent._batch import BatchResult
from cent._command import Command
from cent._errors import ApiError, FailedCommand
from cent._payload import RawJSON


def to_dict(value: Any) -> Any:
    """value - a result, a command, or anything holding them - as the plain
    dicts, lists and values ``json.dumps`` and web frameworks encode, by the
    wire names Centrifugo uses::

        return JSONResponse(cent.to_dict(client.history(channel="news", limit=10)))

    An error in a result - a channel's in a broadcast, a command's in a batch -
    is ``{"code": ..., "message": ...}`` for an ApiError and ``{"message": ...}``
    for any other. A command's payload is the JSON object, not its text.
    Payloads are as they are.
    """
    if isinstance(value, BaseException):
        if isinstance(value, ApiError):
            return {"code": value.code, "message": value.message}
        return {"message": str(value)}
    if isinstance(value, BatchResult):
        return {"replied": value.replied, "failed": to_dict(value.failed)}
    if isinstance(value, FailedCommand):
        return {"index": value.index, "method": value.method, "error": to_dict(value.error)}
    if isinstance(value, Command):
        return {"method": value.method, "payload": json.loads(value.payload)}
    if isinstance(value, RawJSON):
        return json.loads(value.text)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: to_dict(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, dict):
        return {k: to_dict(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_dict(v) for v in value]
    return value
