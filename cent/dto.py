import json
from abc import ABC, abstractmethod
from typing import TypeVar, Any, Generic, TYPE_CHECKING, ClassVar, Optional, List, Dict
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from cent.exceptions import CentDecodeError, CentApiResponseError


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


CentResultType = TypeVar("CentResultType", bound=CentResult)


class Error(BaseModel):
    code: int
    message: str


class Response(BaseModel, Generic[CentResultType]):
    error: Optional[Error] = None
    result: Optional[CentResultType] = None


class CentRequest(BaseModel, Generic[CentResultType], ABC):
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

    @property
    def api_payload(self) -> Any:
        return self.model_dump(exclude_none=True)

    @property
    def api_method(self) -> str:
        return self.__api_method__

    def parse_response(
        self,
        content: str,
    ) -> Response[CentResult]:
        try:
            json_data = json.loads(content)
        except Exception as err:
            raise CentDecodeError from err

        if isinstance(self, BatchRequest):
            json_data = _validate_batch(self, json_data["replies"])

        try:
            response_type = Response[self.__returning__]  # type: ignore
            response = TypeAdapter(response_type).validate_python(
                json_data,
            )
        except ValidationError as err:
            raise CentDecodeError from err

        if response.error:
            raise CentApiResponseError(
                code=response.error.code,
                message=response.error.message,
            )

        return response


class NestedModel(BaseModel, ABC):
    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )


class BatchResult(CentResult):
    """Batch response.

    Attributes:
        replies: List of results from batch request.
    """

    replies: List[CentResult]


class BatchRequest(CentRequest[BatchResult]):
    """Batch request."""

    __returning__ = BatchResult
    __api_method__ = "batch"

    requests: List[Any]
    parallel: Optional[bool] = None

    @property
    def api_payload(self) -> Any:
        commands = [
            {request.__api_method__: request.model_dump(exclude_none=True)}
            for request in self.requests
        ]
        return {"commands": commands, "parallel": bool(self.parallel)}


def _validate_batch(
    request: BatchRequest,
    json_replies: List[Dict[str, Any]],
) -> Dict[str, Dict[str, List[Any]]]:
    replies: List[CentRequest[Any]] = []
    for command_method, json_data in zip(request.requests, json_replies):
        validated_request: CentRequest[Any] = TypeAdapter(
            command_method.__returning__
        ).validate_python(
            json_data[command_method.__api_method__],
        )
        replies.append(validated_request)
    return {"result": {"replies": replies}}


class Disconnect(NestedModel):
    """Disconnect data.

    Attributes:
        code (int): Disconnect code.
        reason (str): Disconnect reason.
    """

    code: int = 0
    reason: str = ""


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

    offset: int = 0
    epoch: str = ""


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

    cpu: float = 0.0
    rss: int = 0


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

    client: str = ""
    user: str = ""
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
    offset: int = 0
    tags: Optional[Dict[str, str]] = None


class Metrics(CentResult):
    """Metrics result.

    Attributes:
        interval (float): Metrics aggregation interval.
        items (Dict[str, float]): metric values.
    """

    interval: float = 0.0
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
    version: str = ""
    num_clients: int = 0
    num_subs: int = 0
    num_users: int = 0
    num_channels: int = 0
    uptime: int = 0
    metrics: Optional[Metrics] = None
    process: Optional[ProcessStats] = None


class PublishResult(CentResult):
    """Publish result.

    Attributes:
        offset: Offset of publication in history stream.
        epoch: Epoch of current stream.
    """

    offset: int = 0
    epoch: str = ""


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

    num_clients: int = 0


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
    offset: int = 0
    epoch: str = ""


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

    num_clients: int = 0
    num_users: int = 0


class RefreshResult(CentResult):
    """Refresh result."""


class SubscribeResult(CentResult):
    """Subscribe result."""


class UnsubscribeResult(CentResult):
    """Unsubscribe result."""


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


class ConnectionTokenInfo(NestedModel):
    """Connection token info."""

    uid: Optional[str] = None
    issued_at: Optional[int] = None


class SubscriptionTokenInfo(NestedModel):
    """Subscription token info."""

    uid: Optional[str] = None
    issued_at: Optional[int] = None


class ChannelContext(NestedModel):
    """Channel context."""

    source: Optional[int] = None


class ConnectionState(NestedModel):
    """Connection state."""

    channels: Optional[Dict[str, ChannelContext]] = None
    connection_token: Optional[ConnectionTokenInfo] = None
    subscription_tokens: Optional[Dict[str, SubscriptionTokenInfo]] = None
    meta: Optional[Any] = None


class ConnectionInfo(NestedModel):
    """Connection info."""

    app_name: str = ""
    app_version: str = ""
    transport: str
    protocol: str
    user: str = ""
    state: Optional[ConnectionState] = None


class ConnectionsResult(CentResult):
    connections: Dict[str, ConnectionInfo]


class ConnectionsRequest(CentRequest[ConnectionsResult]):
    """Connections request."""

    __api_method__ = "connections"
    __returning__ = ConnectionsResult

    user: str
    expression: str


class UpdateUserStatusResult(CentResult):
    """
    Update user status result.
    """


class UpdateUserStatusRequest(CentRequest[UpdateUserStatusResult]):
    """Update user status request."""

    __api_method__ = "update_user_status"
    __returning__ = UpdateUserStatusResult

    users: List[str]


class UserStatus(NestedModel):
    """
    User status.
    """

    user: str
    active: int = 0
    online: int = 0


class GetUserStatusResult(CentResult):
    """
    Get user status result.
    """

    statuses: List[UserStatus]


class GetUserStatusRequest(CentRequest[GetUserStatusResult]):
    """
    Get user status request.
    """

    __api_method__ = "get_user_status"
    __returning__ = GetUserStatusResult

    users: List[str]


class DeleteUserStatusResult(CentResult):
    """
    Delete user status result.
    """


class DeleteUserStatusRequest(CentRequest[DeleteUserStatusResult]):
    """
    Delete user status request.
    """

    __api_method__ = "delete_user_status"
    __returning__ = DeleteUserStatusResult

    users: List[str]


class BlockUserResult(CentResult):
    """
    Block user result.
    """


class BlockUserRequest(CentRequest[BlockUserResult]):
    """
    Block user request.
    """

    __api_method__ = "block_user"
    __returning__ = BlockUserResult

    expire_at: Optional[int] = None
    user: str


class UnblockUserResult(CentResult):
    """
    Unblock user result.
    """


class UnblockUserRequest(CentRequest[UnblockUserResult]):
    """
    Unblock user request.
    """

    __api_method__ = "unblock_user"
    __returning__ = UnblockUserResult

    user: str


class RevokeTokenResult(CentResult):
    """
    Revoke token result.
    """


class RevokeTokenRequest(CentRequest[RevokeTokenResult]):
    """
    Revoke token request.
    """

    __api_method__ = "revoke_token"
    __returning__ = RevokeTokenResult

    expire_at: Optional[int] = None
    uid: str


class InvalidateUserTokensResult(CentResult):
    """
    Invalidate user tokens result.
    """


class InvalidateUserTokensRequest(CentRequest[InvalidateUserTokensResult]):
    """
    Invalidate user tokens request.
    """

    __api_method__ = "invalidate_user_tokens"
    __returning__ = InvalidateUserTokensResult

    expire_at: Optional[int] = None
    user: str
    issued_before: Optional[int] = None
    channel: Optional[str] = None


class DeviceRegisterResult(CentResult):
    """
    Device register result.
    """

    id: str


class DeviceRegisterRequest(CentRequest[DeviceRegisterResult]):
    """
    Device register request.
    """

    __api_method__ = "device_register"
    __returning__ = DeviceRegisterResult

    id: Optional[str] = None
    provider: str
    token: str
    platform: str
    user: Optional[str] = None
    timezone: Optional[str] = None
    locale: Optional[str] = None
    meta: Optional[Dict[str, str]] = None
    topics: Optional[List[str]] = None


class DeviceUserUpdate(NestedModel):
    """
    Device user update.
    """

    user: str


class DeviceTimezoneUpdate(NestedModel):
    """
    Device timezone update.
    """

    timezone: str


class DeviceLocaleUpdate(NestedModel):
    """
    Device locale update.
    """

    locale: str


class DeviceMetaUpdate(NestedModel):
    """
    Device meta update.
    """

    meta: Dict[str, str]


class DeviceTopicsUpdate(NestedModel):
    """
    Device topics update.
    """

    op: str
    topics: List[str]


class DeviceUpdateResult(CentResult):
    """
    Device update result.
    """


class DeviceUpdateRequest(CentRequest[DeviceUpdateResult]):
    """
    Device update request.
    """

    __api_method__ = "device_update"
    __returning__ = DeviceUpdateResult

    ids: Optional[List[str]] = None
    users: Optional[List[str]] = None
    user_update: Optional[DeviceUserUpdate] = None
    timezone_update: Optional[DeviceTimezoneUpdate] = None
    locale_update: Optional[DeviceLocaleUpdate] = None
    meta_update: Optional[DeviceMetaUpdate] = None
    topics_update: Optional[DeviceTopicsUpdate] = None


class DeviceRemoveResult(CentResult):
    """
    Device remove result.
    """


class DeviceRemoveRequest(CentRequest[DeviceRemoveResult]):
    """
    Device remove request.
    """

    __api_method__ = "device_remove"
    __returning__ = DeviceRemoveResult

    ids: Optional[List[str]] = None
    users: Optional[List[str]] = None


class DeviceFilter(NestedModel):
    """
    Device filter.
    """

    ids: Optional[List[str]] = None
    users: Optional[List[str]] = None
    topics: Optional[List[str]] = None
    providers: Optional[List[str]] = None
    platforms: Optional[List[str]] = None


class Device(NestedModel):
    """
    Device.
    """

    id: str
    platform: str = ""
    provider: str = ""
    token: str = ""
    user: str = ""
    created_at: int = 0
    updated_at: int = 0
    meta: Optional[Dict[str, str]] = None
    topics: Optional[List[str]] = None


class DeviceListResult(CentResult):
    """
    Device list result.
    """

    items: List[Device]
    next_cursor: Optional[str] = None
    total_count: Optional[int] = None


class DeviceListRequest(CentRequest[DeviceListResult]):
    """
    Device list request.
    """

    __api_method__ = "device_list"
    __returning__ = DeviceListResult

    filter: Optional[DeviceFilter] = None
    include_total_count: Optional[bool] = None
    include_meta: Optional[bool] = None
    include_topics: Optional[bool] = None
    cursor: Optional[str] = None
    limit: Optional[int] = None


class DeviceTopicFilter(NestedModel):
    """
    Device topic filter.
    """

    device_ids: Optional[List[str]] = None
    device_providers: Optional[List[str]] = None
    device_platforms: Optional[List[str]] = None
    device_users: Optional[List[str]] = None
    topics: Optional[List[str]] = None
    topic_prefix: Optional[str] = None


class DeviceTopic(NestedModel):
    """
    Device topic.
    """

    id: str
    topic: str
    device: Device


class DeviceTopicListResult(CentResult):
    """
    Device topic list result.
    """

    items: List[DeviceTopic]
    next_cursor: Optional[str] = None
    total_count: Optional[int] = None


class DeviceTopicListRequest(CentRequest[DeviceTopicListResult]):
    """
    Device topic list request.
    """

    __api_method__ = "device_topic_list"
    __returning__ = DeviceTopicListResult

    filter: Optional[DeviceTopicFilter] = None
    include_total_count: Optional[bool] = None
    include_device: Optional[bool] = None
    cursor: Optional[str] = None
    limit: Optional[int] = None


class UserTopicFilter(NestedModel):
    """
    User topic filter.
    """

    users: Optional[List[str]] = None
    topics: Optional[List[str]] = None
    topic_prefix: Optional[str] = None


class UserTopic(NestedModel):
    """
    User topic.
    """

    id: str
    user: str = ""
    topic: str


class UserTopicListResult(CentResult):
    """
    User topic list result.
    """

    items: List[UserTopic]
    next_cursor: Optional[str] = None
    total_count: Optional[int] = None


class UserTopicListRequest(CentRequest[UserTopicListResult]):
    """
    User topic list request.
    """

    __api_method__ = "user_topic_list"
    __returning__ = UserTopicListResult

    filter: Optional[UserTopicFilter] = None
    include_total_count: Optional[bool] = None
    cursor: Optional[str] = None
    limit: Optional[int] = None


class DeviceTopicUpdateResult(CentResult):
    """
    Device topic update result.
    """


class DeviceTopicUpdateRequest(CentRequest[DeviceTopicUpdateResult]):
    """
    Device topic update request.
    """

    __api_method__ = "device_topic_update"
    __returning__ = DeviceTopicUpdateResult

    device_id: str
    op: str
    topics: List[str]


class UserTopicUpdateResult(CentResult):
    """
    User topic update result.
    """


class UserTopicUpdateRequest(CentRequest[UserTopicUpdateResult]):
    """
    User topic update request.
    """

    __api_method__ = "user_topic_update"
    __returning__ = UserTopicUpdateResult

    user: str
    op: str
    topics: List[str]


class PushRecipient(NestedModel):
    """
    Push recipient.
    """

    filter: Optional[DeviceFilter] = None
    fcm_tokens: Optional[List[str]] = None
    fcm_topic: Optional[str] = None
    fcm_condition: Optional[str] = None
    hms_tokens: Optional[List[str]] = None
    hms_topic: Optional[str] = None
    hms_condition: Optional[str] = None
    apns_tokens: Optional[List[str]] = None


class FcmPushNotification(NestedModel):
    """
    FCM push notification.
    """

    message: Any


class HmsPushNotification(NestedModel):
    """
    HMS push notification.
    """

    message: Any


class ApnsPushNotification(NestedModel):
    """
    APNS push notification.
    """

    headers: Optional[Dict[str, str]] = None
    payload: Any


class PushNotification(NestedModel):
    """
    Push notification.
    """

    fcm: Optional[FcmPushNotification] = None
    hms: Optional[HmsPushNotification] = None
    apns: Optional[ApnsPushNotification] = None
    expire_at: Optional[int] = None


class SendPushNotificationResult(CentResult):
    """Send push notification result."""

    uid: str


class PushLocalization(NestedModel):
    translations: Dict[str, str]


class RateLimitPolicy(NestedModel):
    rate: int
    interval_ms: int


class PushRateLimitStrategy(NestedModel):
    key: Optional[str] = None
    policies: List[RateLimitPolicy]
    drop_if_rate_limited: Optional[bool] = False


class PushTimeLimitStrategy(NestedModel):
    send_after_time: str  # use "%H:%M:%S" format, ex. "09:00:00"
    send_before_time: str  # use "%H:%M:%S" format, ex. "18:00:00"
    no_tz_send_now: Optional[bool] = False


class PushLimitStrategy(NestedModel):
    rate_limit: Optional[PushRateLimitStrategy] = None
    time_limit: Optional[PushTimeLimitStrategy] = None


class SendPushNotificationRequest(CentRequest[SendPushNotificationResult]):
    """
    Send push notification request.
    """

    __api_method__ = "send_push_notification"
    __returning__ = SendPushNotificationResult

    recipient: PushRecipient
    notification: PushNotification
    uid: Optional[str] = None
    send_at: Optional[int] = None
    analytics_uid: Optional[str] = None
    optimize_for_reliability: Optional[bool] = None
    limit_strategy: Optional[PushLimitStrategy] = None
    localizations: Optional[Dict[str, PushLocalization]] = None
    use_templating: Optional[bool] = None
    use_meta: Optional[bool] = None


class UpdatePushStatusResult(CentResult):
    """
    Update push status result.
    """


class UpdatePushStatusRequest(CentRequest[UpdatePushStatusResult]):
    """
    Update push status request.
    """

    __api_method__ = "update_push_status"
    __returning__ = UpdatePushStatusResult

    analytics_uid: str
    status: str
    device_id: Optional[str] = None
    msg_id: Optional[str] = None


class CancelPushResult(CentResult):
    """
    Cancel push result.
    """


class CancelPushRequest(CentRequest[CancelPushResult]):
    """
    Cancel push request.
    """

    __returning__ = CancelPushResult
    __api_method__ = "cancel_push"

    uid: str
