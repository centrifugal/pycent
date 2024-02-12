import contextlib
import asyncio as _asyncio

from .client import (
    Client,
    AsyncClient,
    GrpcClient,
)
from cent.base import CentRequest
from cent.requests import (
    BroadcastRequest,
    PublishRequest,
    SubscribeRequest,
    UnsubscribeRequest,
    PresenceRequest,
    PresenceStatsRequest,
    HistoryRequest,
    HistoryRemoveRequest,
    RefreshRequest,
    ChannelsRequest,
    DisconnectRequest,
    InfoRequest,
    BatchRequest,
)
from cent.results import (
    PublishResult,
    BroadcastResult,
    SubscribeResult,
    UnsubscribeResult,
    PresenceResult,
    PresenceStatsResult,
    HistoryResult,
    HistoryRemoveResult,
    RefreshResult,
    ChannelsResult,
    DisconnectResult,
    InfoResult,
    BatchResult,
)
from cent.types import (
    StreamPosition,
    ChannelOptionsOverride,
    Disconnect,
    BoolValue,
    ProcessStats,
    Node,
    Publication,
    ClientInfo,
)
from cent.exceptions import (
    CentError,
    CentNetworkError,
    CentTransportError,
    CentUnauthorizedError,
    CentDecodeError,
    CentAPIError,
)

with contextlib.suppress(ImportError):
    import uvloop as _uvloop

    _asyncio.set_event_loop_policy(_uvloop.EventLoopPolicy())

__all__ = (
    "AsyncClient",
    "BatchRequest",
    "BatchResult",
    "BoolValue",
    "BroadcastRequest",
    "BroadcastResult",
    "CentAPIError",
    "CentDecodeError",
    "CentError",
    "CentNetworkError",
    "CentRequest",
    "CentTransportError",
    "CentUnauthorizedError",
    "ChannelOptionsOverride",
    "ChannelsRequest",
    "ChannelsResult",
    "Client",
    "ClientInfo",
    "Disconnect",
    "DisconnectRequest",
    "DisconnectResult",
    "GrpcClient",
    "HistoryRemoveRequest",
    "HistoryRemoveResult",
    "HistoryRequest",
    "HistoryResult",
    "InfoRequest",
    "InfoResult",
    "Node",
    "PresenceRequest",
    "PresenceResult",
    "PresenceStatsRequest",
    "PresenceStatsResult",
    "ProcessStats",
    "Publication",
    "PublishRequest",
    "PublishResult",
    "RefreshRequest",
    "RefreshResult",
    "StreamPosition",
    "SubscribeRequest",
    "SubscribeResult",
    "UnsubscribeRequest",
    "UnsubscribeResult",
)
