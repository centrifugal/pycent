from abc import ABC, abstractmethod
from typing import TypeVar, Any, Generic, TYPE_CHECKING, ClassVar, Optional, List, Dict
from pydantic import BaseModel, ConfigDict, Field


class Error(BaseModel):
    code: int
    message: str


CentType = TypeVar("CentType", bound=Any)


class Response(BaseModel, Generic[CentType]):
    error: Optional[Error] = None
    result: Optional[CentType] = None


class CentRequest(BaseModel, Generic[CentType], ABC):
    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

    if TYPE_CHECKING:
        __returning__: ClassVar[type]
        __api_method__: ClassVar[str]
    else:

        @property
        @abstractmethod
        def __returning__(self) -> type:
            pass

        @property
        @abstractmethod
        def __api_method__(self) -> str:
            pass


class CentResult(BaseModel, ABC):
    model_config = ConfigDict(
        use_enum_values=True,
        extra="allow",
        validate_assignment=True,
        frozen=True,
        populate_by_name=True,
        arbitrary_types_allowed=True,
        defer_build=True,
    )


class NestedModel(BaseModel, ABC):
    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )


class Disconnect(NestedModel):
    """Disconnect data.

    Attributes:
        code (int): Disconnect code.
        reason (str): Disconnect reason.
    """

    code: int
    reason: str


class BoolValue(NestedModel):
    """Bool value.

    Attributes:
        value (bool): Value.
    """

    value: bool


class StreamPosition(NestedModel):
    """
    Stream position representation.

    Attributes:
        offset (int): Offset of publication in history stream.
        epoch (str): Epoch of current stream.
    """

    offset: int
    epoch: str


class ChannelOptionsOverride(NestedModel):
    """
    Override object for channel options.

    Attributes:
        presence (Optional[BoolValue]): Override for presence.
        join_leave (Optional[BoolValue]): Override for join_leave behavior.
        force_push_join_leave (Optional[BoolValue]): Force push for join_leave events.
        force_positioning (Optional[BoolValue]): Override for force positioning.
        force_recovery (Optional[BoolValue]): Override for force recovery.
    """

    presence: Optional[BoolValue] = None
    join_leave: Optional[BoolValue] = None
    force_push_join_leave: Optional[BoolValue] = None
    force_positioning: Optional[BoolValue] = None
    force_recovery: Optional[BoolValue] = None


class ProcessStats(CentResult):
    """
    Represents statistics of a process.

    Attributes:
        cpu (float): Process CPU usage as a percentage. Defaults to 0.0.
        rss (int): Process Resident Set Size (RSS) in bytes.
    """

    cpu: float = Field(default=0.0)
    rss: int


class ClientInfo(CentResult):
    """
    Represents the result containing client information.

    Attributes:
        client (str): Client ID.
        user (str): User ID.
        conn_info (Optional[Any]): Optional connection info. This can include details
            such as IP address, location, etc.
        chan_info (Optional[Any]): Optional channel info. This might include specific
            settings or preferences related to the channel.
    """

    client: str
    user: str
    conn_info: Optional[Any] = None
    chan_info: Optional[Any] = None


class Publication(CentResult):
    """Publication result.

    Attributes:
        offset (int): Offset of publication in history stream.
        data (Any): Custom JSON inside publication.
        tags (Optional[Dict[str, str]]): Tags are optional.
    """

    data: Any
    offset: int = Field(default=0)
    tags: Optional[Dict[str, str]] = None


class Metrics(CentResult):
    """Metrics result.

    Attributes:
        interval (float): Metrics aggregation interval.
        items (Dict[str, float]): metric values.
    """

    interval: float = Field(default=0.0)
    items: Dict[str, float]


class Node(CentResult):
    """Node result.

    Attributes:
        uid (str): Node unique identifier.
        name (str): Node name.
        version (str): Node version.
        num_clients (int): Total number of connections.
        num_subs (int): Total number of subscriptions.
        num_users (int): Total number of users.
        num_channels (int): Total number of channels.
        uptime (int): Node uptime.
        metrics (Optional[Metrics]): Node metrics.
        process (Optional[ProcessStats]): Node process stats.
    """

    uid: str
    name: str
    version: str
    num_clients: int = Field(default=0)
    num_subs: int = Field(default=0)
    num_users: int = Field(default=0)
    num_channels: int = Field(default=0)
    uptime: int = Field(default=0)
    metrics: Optional[Metrics] = None
    process: Optional[ProcessStats] = None


class BatchResult(CentResult):
    """Batch response.

    Attributes:
        replies: List of results from batch request.
    """

    replies: List[Any]


class PublishResult(CentResult):
    """Publish result.

    Attributes:
        offset: Offset of publication in history stream.
        epoch: Epoch of current stream.
    """

    offset: Optional[int] = None
    epoch: Optional[str] = None


class BroadcastResult(CentResult):
    """Broadcast result.

    Attributes:
        responses: List of responses for each individual publish
        (with possible error and publish result)
    """

    responses: List[Response[PublishResult]] = Field(default_factory=list)


class ChannelInfoResult(CentResult):
    """Channel info result.

    Attributes:
        num_clients: Total number of connections currently subscribed to a channel.
    """

    num_clients: int = Field(default=0)


class ChannelsResult(CentResult):
    """Channels result.

    Attributes:
        channels: Map where key is channel and value is ChannelInfoResult.
    """

    channels: Dict[str, ChannelInfoResult]


class DisconnectResult(CentResult):
    """Disconnect result."""


class HistoryRemoveResult(CentResult):
    """History remove result."""


class HistoryResult(CentResult):
    """History result.

    Attributes:
        publications: List of publications in channel.
        offset: Top offset in history stream.
        epoch: Epoch of current stream.
    """

    publications: List[Publication] = Field(default_factory=list)
    offset: Optional[int] = None
    epoch: Optional[str] = None


class InfoResult(CentResult):
    """Info result.

    Attributes:
        nodes: Information about all nodes in a cluster.
    """

    nodes: List[Node]


class PresenceResult(CentResult):
    """Presence result.

    Attributes:
        presence: Map where key is client ID and value is ClientInfo.
    """

    presence: Dict[str, ClientInfo]


class PresenceStatsResult(CentResult):
    """Presence stats result.

    Attributes:
        num_clients: Total number of clients in channel.
        num_users: Total number of unique users in channel.
    """

    num_clients: int = Field(default=0)
    num_users: int = Field(default=0)


class RefreshResult(CentResult):
    """Refresh result."""


class SubscribeResult(CentResult):
    """Subscribe result."""


class UnsubscribeResult(CentResult):
    """Unsubscribe result."""


class BatchRequest(CentRequest[BatchResult]):
    """Batch request.

    Attributes:
        commands: List of commands to execute in batch.
    """

    __returning__ = BatchResult
    __api_method__ = "batch"

    commands: List[CentRequest[Any]]
    parallel: Optional[bool] = None


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

    channel: str


class InfoRequest(CentRequest[InfoResult]):
    """Info request."""

    __returning__ = InfoResult
    __api_method__ = "info"


class PresenceRequest(CentRequest[PresenceResult]):
    """Presence request.

    Attributes:
        channel: Name of channel to call presence from.
    """

    __returning__ = PresenceResult
    __api_method__ = "presence"

    channel: str


class PresenceStatsRequest(CentRequest[PresenceStatsResult]):
    """Presence request.

    Attributes:
        channel: Name of channel to call presence from.
    """

    __returning__ = PresenceStatsResult
    __api_method__ = "presence_stats"

    channel: str


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

    user: str
    channel: str
    client: Optional[str] = None
    session: Optional[str] = None
