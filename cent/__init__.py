"""Python SDK for Centrifugo's HTTP server API.

>>> import cent
>>> client = cent.Client("http://localhost:8000/api", api_key="...")
>>> client.publish(cent.PublishRequest(channel="news", data={"text": "hello"}))

See https://github.com/centrifugal/pycent for the documentation.
"""

from cent import _api
from cent._api import *  # noqa: F403 - the generated request and result types
from cent._batch import AsyncBatch, Batch, BatchResult, Pending
from cent._broadcast import BroadcastResult, ChannelResult
from cent._client import AsyncClient, Client, OnAttemptError
from cent._command import Command, new_command
from cent._core import RequestInfo
from cent._errors import (
    ApiError,
    BadRequestError,
    BatchFailedCommandsError,
    BatchNotSentError,
    BatchSentError,
    BroadcastFailedChannelsError,
    CentError,
    CentTimeoutError,
    ClosedError,
    CommandError,
    ConflictError,
    DecodeError,
    HTTPError,
    InternalError,
    InvalidConfigError,
    InvalidRequestError,
    NetworkError,
    NotAvailableError,
    NotFoundError,
    TooManyRequestsError,
    UnauthorizedError,
    UnknownChannelError,
    UnrecoverablePositionError,
    retryable,
)
from cent._payload import JSON, RawJSON
from cent._retry import BroadcastAttempt, exponential_backoff

__all__ = [
    "JSON",
    "ApiError",
    "AsyncBatch",
    "AsyncClient",
    "BadRequestError",
    "Batch",
    "BatchFailedCommandsError",
    "BatchNotSentError",
    "BatchResult",
    "BatchSentError",
    "BroadcastAttempt",
    "BroadcastFailedChannelsError",
    "BroadcastResult",
    "CentError",
    "CentTimeoutError",
    "ChannelResult",
    "Client",
    "ClosedError",
    "Command",
    "CommandError",
    "ConflictError",
    "DecodeError",
    "HTTPError",
    "InternalError",
    "InvalidConfigError",
    "InvalidRequestError",
    "NetworkError",
    "NotAvailableError",
    "NotFoundError",
    "OnAttemptError",
    "Pending",
    "RawJSON",
    "RequestInfo",
    "TooManyRequestsError",
    "UnauthorizedError",
    "UnknownChannelError",
    "UnrecoverablePositionError",
    "exponential_backoff",
    "new_command",
    "retryable",
]
__all__ += _api.__all__
