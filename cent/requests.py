from typing import Any, Optional, Dict, List

from pydantic import Field

from cent.proto.centrifugal.centrifugo.api import (
    ChannelsRequest as GrpcChannelsRequest,
    PublishRequest as GrpcPublishRequest,
    PresenceStatsRequest as GrpcPresenceStatsRequest,
    InfoRequest as GrpcInfoRequest,
    BroadcastRequest as GrpcBroadcastRequest,
    BatchRequest as GrpcBatchRequest,
    RefreshRequest as GrpcRefreshRequest,
    UnsubscribeRequest as GrpcUnsubscribeRequest,
    SubscribeRequest as GrpcSubscribeRequest,
    HistoryRequest as GrpcHistoryRequest,
    HistoryRemoveRequest as GrpcHistoryRemoveRequest,
    PresenceRequest as GrpcPresenceRequest,
    DisconnectRequest as GrpcDisconnectRequest,
)

from cent.base import CentRequest
from cent.types import StreamPosition, ChannelOptionsOverride, Disconnect

from cent.results import (
    BatchResult, BroadcastResult, ChannelsResult,
    DisconnectResult, HistoryResult, HistoryRemoveResult,
    InfoResult, PresenceResult, PresenceStatsResult,
    PublishResult, RefreshResult, SubscribeResult,
    UnsubscribeResult,
)


class BatchRequest(CentRequest[BatchResult]):
    """Batch request."""

    __returning__ = BatchResult
    __api_method__ = "batch"
    __grpc_method__ = GrpcBatchRequest

    commands: List[CentRequest[Any]]
    """List of commands to execute in batch."""


class BroadcastRequest(CentRequest[BroadcastResult]):
    """Broadcast request."""

    __returning__ = BroadcastResult
    __api_method__ = "broadcast"
    __grpc_method__ = GrpcBroadcastRequest

    channels: List[str]
    """List of channels to publish data to."""
    data: Any
    """Custom JSON data to publish into a channel."""
    skip_history: Optional[bool] = None
    """Skip adding publications to channels' history for this request."""
    tags: Optional[Dict[str, str]] = None
    """Publication tags - map with arbitrary string keys and values which is attached to
    publication and will be delivered to clients."""
    b64data: Optional[str] = Field(None, alias="b64_data")
    """Custom binary data to publish into a channel encoded to base64 so it's possible
    to use HTTP API to send binary to clients. Centrifugo will decode it from base64 before
    publishing. In case of GRPC you can publish binary using data field."""
    idempotency_key: Optional[str] = None
    """Optional idempotency key to drop duplicate publications upon retries. It acts per channel.
    Centrifugo currently keeps the cache of idempotent publish results during 5 minutes window.
    Available since Centrifugo v5.2.0"""


class ChannelsRequest(CentRequest[ChannelsResult]):
    """Channels request."""

    __returning__ = ChannelsResult
    __api_method__ = "channels"
    __grpc_method__ = GrpcChannelsRequest

    pattern: Optional[str] = None
    """Pattern to filter channels, we are using https://github.com/gobwas/glob
    library for matching."""


class DisconnectRequest(CentRequest[DisconnectResult]):
    """Disconnect request."""

    __returning__ = DisconnectResult
    __api_method__ = "disconnect"
    __grpc_method__ = GrpcDisconnectRequest

    user: str
    """User ID to disconnect."""
    client: Optional[str] = None
    """Specific client ID to disconnect (user still required to be set)."""
    session: Optional[str] = None
    """Specific client session to disconnect (user still required to be set)."""
    whitelist: Optional[List[str]] = None
    """Array of client IDs to keep."""
    disconnect: Optional[Disconnect] = None
    """Provide custom disconnect object, see below."""


class HistoryRequest(CentRequest[HistoryResult]):
    """History request."""

    __returning__ = HistoryResult
    __api_method__ = "history"
    __grpc_method__ = GrpcHistoryRequest

    channel: str
    """Name of channel to call history from."""
    limit: Optional[int] = None
    """Limit number of returned publications, if not set in request then only current stream
    position information will present in result (without any publications)."""
    since: Optional[StreamPosition] = None
    """To return publications after this position."""
    reverse: Optional[bool] = None
    """Iterate in reversed order (from latest to earliest)."""


class HistoryRemoveRequest(CentRequest[HistoryRemoveResult]):
    """History remove request."""

    __returning__ = HistoryRemoveResult
    __api_method__ = "history_remove"
    __grpc_method__ = GrpcHistoryRemoveRequest

    channel: str
    """Name of channel to remove history."""


class InfoRequest(CentRequest[InfoResult]):
    """Info request."""

    __returning__ = InfoResult
    __api_method__ = "info"
    __grpc_method__ = GrpcInfoRequest


class PresenceRequest(CentRequest[PresenceResult]):
    """Presence request."""

    __returning__ = PresenceResult
    __api_method__ = "presence"
    __grpc_method__ = GrpcPresenceRequest

    channel: str
    """Name of channel to call presence from."""


class PresenceStatsRequest(CentRequest[PresenceStatsResult]):
    """Presence request."""

    __returning__ = PresenceStatsResult
    __api_method__ = "presence_stats"
    __grpc_method__ = GrpcPresenceStatsRequest

    channel: str
    """Name of channel to call presence from."""


class PublishRequest(CentRequest[PublishResult]):
    """Publish request."""

    __returning__ = PublishResult
    __api_method__ = "publish"
    __grpc_method__ = GrpcPublishRequest

    channel: str
    """Name of channel to publish."""
    data: Any
    """Custom JSON data to publish into a channel."""
    skip_history: Optional[bool] = None
    """Skip adding publication to history for this request."""
    tags: Optional[Dict[str, str]] = None
    """Publication tags - map with arbitrary string keys and values which is attached to
    publication and will be delivered to clients."""
    b64data: Optional[str] = Field(None, alias="b64_data")
    """Custom binary data to publish into a channel encoded to base64 so it's possible to use
    HTTP API to send binary to clients. Centrifugo will decode it from base64 before publishing.
    In case of GRPC you can publish binary using data field."""
    idempotency_key: Optional[str] = None
    """Optional idempotency key to drop duplicate publications upon retries. It acts per channel.
    Centrifugo currently keeps the cache of idempotent publish results during 5 minutes window.
    Available since Centrifugo v5.2.0"""


class RefreshRequest(CentRequest[RefreshResult]):
    """Refresh request."""

    __returning__ = RefreshResult
    __api_method__ = "refresh"
    __grpc_method__ = GrpcRefreshRequest

    user: str
    """User ID to refresh."""
    client: Optional[str] = None
    """Client ID to refresh (user still required to be set)."""
    session: Optional[str] = None
    """Specific client session to refresh (user still required to be set)."""
    expired: Optional[bool] = None
    """Mark connection as expired and close with Disconnect Expired reason."""
    expire_at: Optional[int] = None
    """Unix time (in seconds) in the future when the connection will expire."""


class SubscribeRequest(CentRequest[SubscribeResult]):
    """Subscribe request."""

    __returning__ = SubscribeResult
    __api_method__ = "subscribe"
    __grpc_method__ = GrpcSubscribeRequest

    user: str
    """User ID to subscribe."""
    channel: str
    """Name of channel to subscribe user to."""
    info: Optional[Any] = None
    """Attach custom data to subscription (will be used in presence and join/leave messages)."""
    b64info: Optional[str] = Field(None, alias="b64_info")
    """info in base64 for binary mode (will be decoded by Centrifugo)."""
    client: Optional[str] = None
    """Specific client ID to subscribe (user still required to be set, will ignore other user
    connections with different client IDs)."""
    session: Optional[str] = None
    """Specific client session to subscribe (user still required to be set)."""
    data: Optional[Any] = None
    """Custom subscription data (will be sent to client in Subscribe push)."""
    b64data: Optional[str] = Field(None, alias="b64_data")
    """Same as data but in base64 format (will be decoded by Centrifugo)."""
    recover_since: Optional[StreamPosition] = None
    """Stream position to recover from."""
    override: Optional[ChannelOptionsOverride] = None
    """Allows dynamically override some channel options defined in Centrifugo
    configuration (see below available fields)."""


class UnsubscribeRequest(CentRequest[UnsubscribeResult]):
    """Unsubscribe request."""

    __returning__ = UnsubscribeResult
    __api_method__ = "unsubscribe"
    __grpc_method__ = GrpcUnsubscribeRequest

    user: str
    """User ID to unsubscribe."""
    channel: str
    """Name of channel to unsubscribe user to."""
    client: Optional[str] = None
    """Specific client ID to unsubscribe (user still required to be set)."""
    session: Optional[str] = None
    """Specific client session to disconnect (user still required to be set)."""
