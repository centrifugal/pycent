"""Commands for Centrifugo's async consumers."""

from __future__ import annotations

import json
from dataclasses import dataclass

from cent import _wire as _w
from cent._api import Request
from cent._validate import method_of, validate


@dataclass(frozen=True, slots=True)
class Command:
    """An API call left for Centrifugo's async consumers to make: written to a
    PostgreSQL outbox table, a Kafka topic, a Redis stream. See
    https://centrifugal.dev/docs/server/consumers.

    Consumers take it as its method and payload apart - the outbox table's
    method and payload columns, a message attribute - or as the JSON message
    ``{"method": ..., "payload": ...}`` of to_json (Kafka, NATS JetStream).

    Within a partition a consumer keeps commands in order: a channel's
    commands keep their order only when every writer derives their partition
    from the channel the same way - the channel as a Kafka message key, say.
    """

    method: str
    """The API method, such as "publish"."""

    payload: str
    """The request, as JSON text."""

    def to_json(self) -> str:
        """The command as one JSON message: ``{"method": ..., "payload": ...}``."""
        return '{"method":' + json.dumps(self.method) + ',"payload":' + self.payload + "}"


def new_command(request: Request) -> Command:
    """The command making the API call request. The request is checked as a
    Client checks it before sending - an invalid one raises
    InvalidRequestError here, rather than in Centrifugo, whose consumers drop
    a command they cannot run - and encoded.

    >>> cmd = cent.new_command(cent.PublishRequest(channel="news", data={"text": "hi"}))
    >>> cur.execute("INSERT INTO centrifugo_outbox (method, payload, partition) VALUES (%s, %s, 0)",
    ...             (cmd.method, cmd.payload))
    """
    method = method_of(request)
    validate(request)
    return Command(method=method, payload=_w.encode(request._to_wire(), method).decode("utf-8"))
