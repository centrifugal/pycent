"""Python SDK for Centrifugo's HTTP server API.

>>> import cent
>>> client = cent.Client("http://localhost:8000/api", api_key="...")
>>> client.publish(channel="news", data={"text": "hello"})

See https://github.com/centrifugal/pycent for the documentation.
"""

from cent import _api
from cent._api import *  # noqa: F403 - the generated request and result types
from cent._autobatch import AutoBatch, BatchContext
from cent._batch import AsyncBatch, Batch, BatchResult, Pending
from cent._broadcast import BroadcastResult, ChannelResult
from cent._client import AsyncClient, BroadcastAttemptCallback, Client
from cent._command import Command
from cent._commands import Commands, command
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
    ConflictError,
    DecodeError,
    FailedCommand,
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
from cent._http import HTTPRequest, HTTPResponse
from cent._payload import JSON, RawJSON
from cent._retry import BroadcastAttempt, exponential_backoff

__all__ = [
    "JSON",
    "ApiError",
    "AsyncBatch",
    "AsyncClient",
    "AutoBatch",
    "BadRequestError",
    "Batch",
    "BatchContext",
    "BatchFailedCommandsError",
    "BatchNotSentError",
    "BatchResult",
    "BatchSentError",
    "BroadcastAttempt",
    "BroadcastAttemptCallback",
    "BroadcastFailedChannelsError",
    "BroadcastResult",
    "CentError",
    "CentTimeoutError",
    "ChannelResult",
    "Client",
    "ClosedError",
    "Command",
    "Commands",
    "ConflictError",
    "DecodeError",
    "FailedCommand",
    "HTTPError",
    "HTTPRequest",
    "HTTPResponse",
    "InternalError",
    "InvalidConfigError",
    "InvalidRequestError",
    "NetworkError",
    "NotAvailableError",
    "NotFoundError",
    "Pending",
    "RawJSON",
    "RequestInfo",
    "TooManyRequestsError",
    "UnauthorizedError",
    "UnknownChannelError",
    "UnrecoverablePositionError",
    "command",
    "exponential_backoff",
    "retryable",
]
__all__ += _api.__all__
