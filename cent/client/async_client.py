from typing import Optional, Any, cast

from aiohttp import ClientSession

from cent.client.session import AiohttpSession
from cent.dto import (
    CentRequest,
    CentResultType,
    PublishResult,
    PublishRequest,
    BroadcastRequest,
    BroadcastResult,
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
)


class AsyncClient:
    def __init__(
        self,
        api_url: str,
        api_key: str,
        timeout: Optional[float] = 10.0,
        session: Optional[ClientSession] = None,
    ) -> None:
        """
        Creates new AsyncClient instance.

        Args:
            api_url (str): Centrifugo API URL.
            api_key (str): Centrifugo API key.
            timeout (float): Base timeout for all requests in seconds.
            session (aiohttp.ClientSession): Custom `aiohttp` session.
        """
        self._api_key = api_key
        self._session = AiohttpSession(
            api_url,
            timeout=timeout,
            session=session,
        )

    async def _send(
        self,
        request: CentRequest[CentResultType],
        timeout: Optional[float] = None,
    ) -> CentResultType:
        method = request.api_method
        payload = request.api_payload
        content = await self._session.make_request(
            self._api_key,
            method,
            payload,
            timeout=timeout,
        )
        response = request.parse_response(content)
        return cast(CentResultType, response.result)

    async def publish(
        self,
        request: PublishRequest,
        timeout: Optional[float] = None,
    ) -> PublishResult:
        return await self._send(request, timeout=timeout)

    async def broadcast(
        self,
        request: BroadcastRequest,
        timeout: Optional[float] = None,
    ) -> BroadcastResult:
        return await self._send(request, timeout=timeout)

    async def subscribe(
        self,
        request: SubscribeRequest,
        timeout: Optional[float] = None,
    ) -> SubscribeResult:
        return await self._send(request, timeout=timeout)

    async def unsubscribe(
        self,
        request: UnsubscribeRequest,
        timeout: Optional[float] = None,
    ) -> UnsubscribeResult:
        return await self._send(request, timeout=timeout)

    async def disconnect(
        self,
        request: DisconnectRequest,
        timeout: Optional[float] = None,
    ) -> DisconnectResult:
        return await self._send(request, timeout=timeout)

    async def presence(
        self,
        request: PresenceRequest,
        timeout: Optional[float] = None,
    ) -> PresenceResult:
        return await self._send(request, timeout=timeout)

    async def presence_stats(
        self,
        request: PresenceStatsRequest,
        timeout: Optional[float] = None,
    ) -> PresenceStatsResult:
        return await self._send(request, timeout=timeout)

    async def history(
        self,
        request: HistoryRequest,
        timeout: Optional[float] = None,
    ) -> HistoryResult:
        return await self._send(request, timeout=timeout)

    async def history_remove(
        self,
        request: HistoryRemoveRequest,
        timeout: Optional[float] = None,
    ) -> HistoryRemoveResult:
        return await self._send(request, timeout=timeout)

    async def info(
        self,
        request: InfoRequest,
        timeout: Optional[float] = None,
    ) -> InfoResult:
        return await self._send(request, timeout=timeout)

    async def refresh(
        self,
        request: RefreshRequest,
        timeout: Optional[float] = None,
    ) -> RefreshResult:
        return await self._send(request, timeout=timeout)

    async def channels(
        self,
        request: ChannelsRequest,
        timeout: Optional[float] = None,
    ) -> ChannelsResult:
        return await self._send(request, timeout=timeout)

    async def connections(
        self,
        request: ConnectionsRequest,
        timeout: Optional[float] = None,
    ) -> ConnectionsResult:
        return await self._send(request, timeout=timeout)

    async def update_user_status(
        self,
        request: UpdateUserStatusRequest,
        timeout: Optional[float] = None,
    ) -> UpdateUserStatusResult:
        return await self._send(request, timeout=timeout)

    async def get_user_status(
        self,
        request: GetUserStatusRequest,
        timeout: Optional[float] = None,
    ) -> GetUserStatusResult:
        return await self._send(request, timeout=timeout)

    async def delete_user_status(
        self,
        request: DeleteUserStatusRequest,
        timeout: Optional[float] = None,
    ) -> DeleteUserStatusResult:
        return await self._send(request, timeout=timeout)

    async def block_user(
        self,
        request: BlockUserRequest,
        timeout: Optional[float] = None,
    ) -> BlockUserResult:
        return await self._send(request, timeout=timeout)

    async def unblock_user(
        self,
        request: UnblockUserRequest,
        timeout: Optional[float] = None,
    ) -> UnblockUserResult:
        return await self._send(request, timeout=timeout)

    async def revoke_token(
        self,
        request: RevokeTokenRequest,
        timeout: Optional[float] = None,
    ) -> RevokeTokenResult:
        return await self._send(request, timeout=timeout)

    async def invalidate_user_tokens(
        self,
        request: InvalidateUserTokensRequest,
        timeout: Optional[float] = None,
    ) -> InvalidateUserTokensResult:
        return await self._send(request, timeout=timeout)

    async def device_register(
        self,
        request: DeviceRegisterRequest,
        timeout: Optional[float] = None,
    ) -> DeviceRegisterResult:
        return await self._send(request, timeout=timeout)

    async def device_update(
        self,
        request: DeviceUpdateRequest,
        timeout: Optional[float] = None,
    ) -> DeviceUpdateResult:
        return await self._send(request, timeout=timeout)

    async def device_remove(
        self,
        request: DeviceRemoveRequest,
        timeout: Optional[float] = None,
    ) -> DeviceRemoveResult:
        return await self._send(request, timeout=timeout)

    async def device_list(
        self,
        request: DeviceListRequest,
        timeout: Optional[float] = None,
    ) -> DeviceListResult:
        return await self._send(request, timeout=timeout)

    async def device_topic_list(
        self,
        request: DeviceTopicListRequest,
        timeout: Optional[float] = None,
    ) -> DeviceTopicListResult:
        return await self._send(request, timeout=timeout)

    async def device_topic_update(
        self,
        request: DeviceTopicUpdateRequest,
        timeout: Optional[float] = None,
    ) -> DeviceTopicUpdateResult:
        return await self._send(request, timeout=timeout)

    async def user_topic_list(
        self,
        request: UserTopicListRequest,
        timeout: Optional[float] = None,
    ) -> UserTopicListResult:
        return await self._send(request, timeout=timeout)

    async def user_topic_update(
        self,
        request: UserTopicUpdateRequest,
        timeout: Optional[float] = None,
    ) -> UserTopicUpdateResult:
        return await self._send(request, timeout=timeout)

    async def send_push_notification(
        self,
        request: SendPushNotificationRequest,
        timeout: Optional[float] = None,
    ) -> SendPushNotificationResult:
        return await self._send(request, timeout=timeout)

    async def update_push_status(
        self,
        request: UpdatePushStatusRequest,
        timeout: Optional[float] = None,
    ) -> UpdatePushStatusResult:
        return await self._send(request, timeout=timeout)

    async def cancel_push(
        self,
        request: CancelPushRequest,
        timeout: Optional[float] = None,
    ) -> CancelPushResult:
        return await self._send(request, timeout=timeout)

    async def batch(
        self,
        request: BatchRequest,
        timeout: Optional[float] = None,
    ) -> BatchResult:
        return await self._send(request, timeout=timeout)

    async def close(self) -> None:
        await self._session.close()

    async def __aenter__(self) -> "AsyncClient":
        return self

    async def __aexit__(self, *kwargs: Any) -> None:
        await self.close()
