import contextlib
import asyncio as _asyncio

from .client import (
    Client,
    AsyncClient,
    GrpcClient,
    BaseSession,
    BaseAsyncSession,
    BaseSyncSession,
    RequestsSession,
    AiohttpSession,
)

from .__meta__ import __version__

with contextlib.suppress(ImportError):
    import uvloop as _uvloop

    _asyncio.set_event_loop_policy(_uvloop.EventLoopPolicy())

__all__ = (
    "__version__",
    "types",
    "methods",
    "exceptions",
    "Client",
    "AsyncClient",
    "BaseSession",
    "BaseAsyncSession",
    "BaseSyncSession",
    "RequestsSession",
    "AiohttpSession",
    "GrpcClient",
)
