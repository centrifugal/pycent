from typing import Optional, Any, cast

from requests import Session
from cent.client.session import RequestsSession
from cent.dto import (
    CentRequest,
    CentResultType,
    BatchResult,
    BatchRequest,
    CancelPushResult,
    CancelPushRequest,
    UpdatePushStatusResult,
    UpdatePushStatusRequest,
    SendPushNotificationResult,
    SendPushNotificationRequest,
    UserTopicUpdateResult,
    UserTopicUpdateRequest,
    UserTopicListResult,
    UserTopicListRequest,
    DeviceTopicUpdateResult,
    DeviceTopicUpdateRequest,
    DeviceTopicListResult,
    DeviceTopicListRequest,
    DeviceListResult,
    DeviceListRequest,
    DeviceRemoveResult,
    DeviceRemoveRequest,
    DeviceUpdateResult,
    DeviceUpdateRequest,
    DeviceRegisterResult,
    DeviceRegisterRequest,
    InvalidateUserTokensResult,
    InvalidateUserTokensRequest,
    RevokeTokenResult,
    RevokeTokenRequest,
    UnblockUserResult,
    UnblockUserRequest,
    BlockUserResult,
    BlockUserRequest,
    DeleteUserStatusResult,
    DeleteUserStatusRequest,
    GetUserStatusResult,
    GetUserStatusRequest,
    UpdateUserStatusResult,
    UpdateUserStatusRequest,
    ConnectionsResult,
    ConnectionsRequest,
    ChannelsResult,
    ChannelsRequest,
    RefreshResult,
    RefreshRequest,
    InfoResult,
    InfoRequest,
    HistoryRemoveResult,
    HistoryRemoveRequest,
    HistoryResult,
    HistoryRequest,
    PresenceStatsResult,
    PresenceStatsRequest,
    PresenceResult,
    PresenceRequest,
    DisconnectResult,
    DisconnectRequest,
    UnsubscribeResult,
    UnsubscribeRequest,
    SubscribeResult,
    SubscribeRequest,
    BroadcastResult,
    BroadcastRequest,
    PublishResult,
    PublishRequest,
)


class Client:
    def __init__(
        self,
        api_url: str,
        api_key: str,
        timeout: Optional[float] = 10.0,
        session: Optional[Session] = None,
    ) -> None:
        """
        Creates new Client instance.

        Args:
            api_url (str): Centrifugo API URL.
            api_key (str): Centrifugo API key.
            timeout (float): Base timeout for all requests in seconds.
            session (requests.Session): Custom `requests` session.
        """

        self._api_url = api_url
        self._api_key = api_key
        self._session = RequestsSession(
            api_url,
            timeout=timeout,
            session=session,
        )

    def _send(
        self,
        request: CentRequest[CentResultType],
        timeout: Optional[float] = None,
    ) -> CentResultType:
        content = self._session.make_request(
            self._api_key,
            request.api_method,
            request.api_payload,
            timeout=timeout,
        )
        response = request.parse_response(content)
        return cast(CentResultType, response.result)

    def publish(
        self,
        request: PublishRequest,
        timeout: Optional[float] = None,
    ) -> PublishResult:
        return self._send(request, timeout=timeout)

    def broadcast(
        self,
        request: BroadcastRequest,
        timeout: Optional[float] = None,
    ) -> BroadcastResult:
        return self._send(request, timeout=timeout)

    def subscribe(
        self,
        request: SubscribeRequest,
        timeout: Optional[float] = None,
    ) -> SubscribeResult:
        return self._send(request, timeout=timeout)

    def unsubscribe(
        self,
        request: UnsubscribeRequest,
        timeout: Optional[float] = None,
    ) -> UnsubscribeResult:
        return self._send(request, timeout=timeout)

    def disconnect(
        self,
        request: DisconnectRequest,
        timeout: Optional[float] = None,
    ) -> DisconnectResult:
        return self._send(request, timeout=timeout)

    def presence(
        self,
        request: PresenceRequest,
        timeout: Optional[float] = None,
    ) -> PresenceResult:
        return self._send(request, timeout=timeout)

    def presence_stats(
        self,
        request: PresenceStatsRequest,
        timeout: Optional[float] = None,
    ) -> PresenceStatsResult:
        return self._send(request, timeout=timeout)

    def history(
        self,
        request: HistoryRequest,
        timeout: Optional[float] = None,
    ) -> HistoryResult:
        return self._send(request, timeout=timeout)

    def history_remove(
        self,
        request: HistoryRemoveRequest,
        timeout: Optional[float] = None,
    ) -> HistoryRemoveResult:
        return self._send(request, timeout=timeout)

    def info(
        self,
        request: InfoRequest,
        timeout: Optional[float] = None,
    ) -> InfoResult:
        return self._send(request, timeout=timeout)

    def refresh(
        self,
        request: RefreshRequest,
        timeout: Optional[float] = None,
    ) -> RefreshResult:
        return self._send(request, timeout=timeout)

    def channels(
        self,
        request: ChannelsRequest,
        timeout: Optional[float] = None,
    ) -> ChannelsResult:
        return self._send(request, timeout=timeout)

    def connections(
        self,
        request: ConnectionsRequest,
        timeout: Optional[float] = None,
    ) -> ConnectionsResult:
        return self._send(request, timeout=timeout)

    def update_user_status(
        self,
        request: UpdateUserStatusRequest,
        timeout: Optional[float] = None,
    ) -> UpdateUserStatusResult:
        return self._send(request, timeout=timeout)

    def get_user_status(
        self,
        request: GetUserStatusRequest,
        timeout: Optional[float] = None,
    ) -> GetUserStatusResult:
        return self._send(request, timeout=timeout)

    def delete_user_status(
        self,
        request: DeleteUserStatusRequest,
        timeout: Optional[float] = None,
    ) -> DeleteUserStatusResult:
        return self._send(request, timeout=timeout)

    def block_user(
        self,
        request: BlockUserRequest,
        timeout: Optional[float] = None,
    ) -> BlockUserResult:
        return self._send(request, timeout=timeout)

    def unblock_user(
        self,
        request: UnblockUserRequest,
        timeout: Optional[float] = None,
    ) -> UnblockUserResult:
        return self._send(request, timeout=timeout)

    def revoke_token(
        self,
        request: RevokeTokenRequest,
        timeout: Optional[float] = None,
    ) -> RevokeTokenResult:
        return self._send(request, timeout=timeout)

    def invalidate_user_tokens(
        self,
        request: InvalidateUserTokensRequest,
        timeout: Optional[float] = None,
    ) -> InvalidateUserTokensResult:
        return self._send(request, timeout=timeout)

    def device_register(
        self,
        request: DeviceRegisterRequest,
        timeout: Optional[float] = None,
    ) -> DeviceRegisterResult:
        return self._send(request, timeout=timeout)

    def device_update(
        self,
        request: DeviceUpdateRequest,
        timeout: Optional[float] = None,
    ) -> DeviceUpdateResult:
        return self._send(request, timeout=timeout)

    def device_remove(
        self,
        request: DeviceRemoveRequest,
        timeout: Optional[float] = None,
    ) -> DeviceRemoveResult:
        return self._send(request, timeout=timeout)

    def device_list(
        self,
        request: DeviceListRequest,
        timeout: Optional[float] = None,
    ) -> DeviceListResult:
        return self._send(request, timeout=timeout)

    def device_topic_list(
        self,
        request: DeviceTopicListRequest,
        timeout: Optional[float] = None,
    ) -> DeviceTopicListResult:
        return self._send(request, timeout=timeout)

    def device_topic_update(
        self,
        request: DeviceTopicUpdateRequest,
        timeout: Optional[float] = None,
    ) -> DeviceTopicUpdateResult:
        return self._send(request, timeout=timeout)

    def user_topic_list(
        self,
        request: UserTopicListRequest,
        timeout: Optional[float] = None,
    ) -> UserTopicListResult:
        return self._send(request, timeout=timeout)

    def user_topic_update(
        self,
        request: UserTopicUpdateRequest,
        timeout: Optional[float] = None,
    ) -> UserTopicUpdateResult:
        return self._send(request, timeout=timeout)

    def send_push_notification(
        self,
        request: SendPushNotificationRequest,
        timeout: Optional[float] = None,
    ) -> SendPushNotificationResult:
        return self._send(request, timeout=timeout)

    def update_push_status(
        self,
        request: UpdatePushStatusRequest,
        timeout: Optional[float] = None,
    ) -> UpdatePushStatusResult:
        return self._send(request, timeout=timeout)

    def cancel_push(
        self,
        request: CancelPushRequest,
        timeout: Optional[float] = None,
    ) -> CancelPushResult:
        return self._send(request, timeout=timeout)

    def batch(
        self,
        request: BatchRequest,
        timeout: Optional[float] = None,
    ) -> BatchResult:
        return self._send(request, timeout=timeout)

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, *kwargs: Any) -> None:
        self.close()
