from typing import Any, Optional, Dict, List

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
    BatchResult,
    BroadcastResult,
    ChannelsResult,
    DisconnectResult,
    HistoryResult,
    HistoryRemoveResult,
    InfoResult,
    PresenceResult,
    PresenceStatsResult,
    PublishResult,
    RefreshResult,
    SubscribeResult,
    UnsubscribeResult,
)


class BatchRequest(CentRequest[BatchResult]):
    """Batch request.

    Attributes:
        commands: List of commands to execute in batch.
    """

    __returning__ = BatchResult
    __api_method__ = "batch"
    __grpc_method__ = GrpcBatchRequest

    commands: List[CentRequest[Any]]
    """List of commands to execute in batch."""


class BroadcastRequest(CentRequest[BroadcastResult]):
    """Broadcast request.

    Attributes:
        channels: List of channels to publish data to.
        data: Custom data to publish into a channel.
        skip_history: Skip adding publications to channels' history for this request.
        tags: Publication tags - map with arbitrary string keys and values which is attached to
            publication and will be delivered to clients.
        b64data: Custom binary data to publish into a channel encoded to base64, so it's possible
            to use HTTP API to send binary to clients. Centrifugo will decode it from base64 before
            publishing. In case of GRPC you can publish binary using data field.
        idempotency_key: Optional idempotency key to drop duplicate publications upon retries. It
            acts per channel. Centrifugo currently keeps the cache of idempotent publish results
            during 5 minutes window. Available since Centrifugo v5.2.0
    """

    __returning__ = BroadcastResult
    __api_method__ = "broadcast"
    __grpc_method__ = GrpcBroadcastRequest

    channels: List[str]
    data: Any
    skip_history: Optional[bool] = None
    tags: Optional[Dict[str, str]] = None
    b64data: Optional[str] = None
    idempotency_key: Optional[str] = None


class ChannelsRequest(CentRequest[ChannelsResult]):
    """Channels request.

    Attributes:
        pattern: Pattern to filter channels, we are using https://github.com/gobwas/glob
        library for matching.
    """

    __returning__ = ChannelsResult
    __api_method__ = "channels"
    __grpc_method__ = GrpcChannelsRequest

    pattern: Optional[str] = None


class DisconnectRequest(CentRequest[DisconnectResult]):
    """Disconnect request.

    Attributes:
        user: User ID to disconnect.
        client: Specific client ID to disconnect (user still required to be set).
        session: Specific client session to disconnect (user still required to be set).
        whitelist: Array of client IDs to keep.
        disconnect: Provide custom disconnect object.
    """

    __returning__ = DisconnectResult
    __api_method__ = "disconnect"
    __grpc_method__ = GrpcDisconnectRequest

    user: str
    client: Optional[str] = None
    session: Optional[str] = None
    whitelist: Optional[List[str]] = None
    disconnect: Optional[Disconnect] = None


class HistoryRequest(CentRequest[HistoryResult]):
    """History request.

    Attributes:
        channel: Name of channel to call history from.
        limit: Limit number of returned publications, if not set in request then only
            current stream position information will present in result (without any publications).
        since: Return publications after this position.
        reverse: Iterate in reversed order (from latest to earliest).
    """

    __returning__ = HistoryResult
    __api_method__ = "history"
    __grpc_method__ = GrpcHistoryRequest

    channel: str
    limit: Optional[int] = None
    since: Optional[StreamPosition] = None
    reverse: Optional[bool] = None


class HistoryRemoveRequest(CentRequest[HistoryRemoveResult]):
    """History remove request.

    Attributes:
        channel: Name of channel to remove history.
    """

    __returning__ = HistoryRemoveResult
    __api_method__ = "history_remove"
    __grpc_method__ = GrpcHistoryRemoveRequest

    channel: str


class InfoRequest(CentRequest[InfoResult]):
    """Info request."""

    __returning__ = InfoResult
    __api_method__ = "info"
    __grpc_method__ = GrpcInfoRequest


class PresenceRequest(CentRequest[PresenceResult]):
    """Presence request.

    Attributes:
        channel: Name of channel to call presence from.
    """

    __returning__ = PresenceResult
    __api_method__ = "presence"
    __grpc_method__ = GrpcPresenceRequest

    channel: str


class PresenceStatsRequest(CentRequest[PresenceStatsResult]):
    """Presence request."""

    __returning__ = PresenceStatsResult
    __api_method__ = "presence_stats"
    __grpc_method__ = GrpcPresenceStatsRequest

    channel: str
    """Name of channel to call presence from."""


class PublishRequest(CentRequest[PublishResult]):
    """Publish request.

    Attributes:
        channel: Name of channel to publish.
        data: Custom data to publish into a channel.
        skip_history: Skip adding publication to history for this request.
        tags: Publication tags - map with arbitrary string keys and values which is attached to
            publication and will be delivered to clients.
        b64data: Custom binary data to publish into a channel encoded to base64, so it's possible
            to use HTTP API to send binary to clients. Centrifugo will decode it from base64
            before publishing. In case of GRPC you can publish binary using data field.
        idempotency_key: Optional idempotency key to drop duplicate publications upon retries.
            It acts per channel. Centrifugo currently keeps the cache of idempotent publish
            results during 5 minutes window. Available since Centrifugo v5.2.0
    """

    __returning__ = PublishResult
    __api_method__ = "publish"
    __grpc_method__ = GrpcPublishRequest

    channel: str
    data: Any
    skip_history: Optional[bool] = None
    tags: Optional[Dict[str, str]] = None
    b64data: Optional[str] = None
    idempotency_key: Optional[str] = None


class RefreshRequest(CentRequest[RefreshResult]):
    """Refresh request.

    Attributes:
        user: User ID to refresh.
        client: Client ID to refresh (user still required to be set).
        session: Specific client session to refresh (user still required to be set).
        expired: Mark connection as expired and close with Disconnect Expired reason.
        expire_at: Unix time (in seconds) in the future when the connection will expire.
    """

    __returning__ = RefreshResult
    __api_method__ = "refresh"
    __grpc_method__ = GrpcRefreshRequest

    user: str
    client: Optional[str] = None
    session: Optional[str] = None
    expired: Optional[bool] = None
    expire_at: Optional[int] = None


class SubscribeRequest(CentRequest[SubscribeResult]):
    """Subscribe request.

    Attributes:
        user: User ID to subscribe.
        channel: Name of channel to subscribe user to.
        info: Attach custom data to subscription (will be used in presence and join/leave
            messages).
        b64info: info in base64 for binary mode (will be decoded by Centrifugo).
        client: Specific client ID to subscribe (user still required to be set, will ignore other
            user connections with different client IDs).
        session: Specific client session to subscribe (user still required to be set).
        data: Custom subscription data (will be sent to client in Subscribe push).
        b64data: Same as data but in base64 format (will be decoded by Centrifugo).
        recover_since: Stream position to recover from.
        override: Allows dynamically override some channel options defined in Centrifugo
            configuration (see below available fields).
    """

    __returning__ = SubscribeResult
    __api_method__ = "subscribe"
    __grpc_method__ = GrpcSubscribeRequest

    user: str
    channel: str
    info: Optional[Any] = None
    b64info: Optional[str] = None
    client: Optional[str] = None
    session: Optional[str] = None
    data: Optional[Any] = None
    b64data: Optional[str] = None
    recover_since: Optional[StreamPosition] = None
    override: Optional[ChannelOptionsOverride] = None


class UnsubscribeRequest(CentRequest[UnsubscribeResult]):
    """Unsubscribe request.

    Attributes:
        user: User ID to unsubscribe.
        channel: Name of channel to unsubscribe user to.
        client: Specific client ID to unsubscribe (user still required to be set).
        session: Specific client session to disconnect (user still required to be set).
    """

    __returning__ = UnsubscribeResult
    __api_method__ = "unsubscribe"
    __grpc_method__ = GrpcUnsubscribeRequest

    user: str
    channel: str
    client: Optional[str] = None
    session: Optional[str] = None
