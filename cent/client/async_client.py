from typing import List, Optional, Any, Dict, TypeVar

from cent.client.session import BaseAsyncSession, AiohttpSession
from cent.methods import (
    CentRequest,
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
)
from cent.methods.batch import BatchRequest
from cent.types import (
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
    StreamPosition,
    ChannelOptionsOverride,
    Disconnect,
)
from cent.types.batch_result import BatchResult

T = TypeVar("T")


class AsyncClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        session: Optional[BaseAsyncSession] = None,
    ) -> None:
        """
        :param base_url: Centrifuge base_url
        :param api_key: Centrifuge API key
        :param session: Custom Session instance
        """

        self._base_url = base_url
        self.api_key = api_key
        self.session = session or AiohttpSession(base_url=base_url)

    async def publish(
        self,
        channel: str,
        data: Any,
        skip_history: Optional[bool] = None,
        tags: Optional[Dict[str, str]] = None,
        b64data: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        request_timeout: Optional[float] = None,
    ) -> PublishResult:
        call = PublishRequest(
            channel=channel,
            data=data,
            skip_history=skip_history,
            tags=tags,
            b64data=b64data,
            idempotency_key=idempotency_key,
        )
        return await self(call, request_timeout=request_timeout)

    async def broadcast(
        self,
        channels: List[str],
        data: Any,
        skip_history: Optional[bool] = None,
        tags: Optional[Dict[str, str]] = None,
        b64data: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        request_timeout: Optional[float] = None,
    ) -> BroadcastResult:
        call = BroadcastRequest(
            channels=channels,
            data=data,
            skip_history=skip_history,
            tags=tags,
            b64data=b64data,
            idempotency_key=idempotency_key,
        )
        return await self(call, request_timeout=request_timeout)

    async def subscribe(
        self,
        user: str,
        channel: str,
        info: Optional[Any] = None,
        b64info: Optional[str] = None,
        client: Optional[str] = None,
        session: Optional[str] = None,
        data: Optional[Any] = None,
        b64data: Optional[str] = None,
        recover_since: Optional[StreamPosition] = None,
        override: Optional[ChannelOptionsOverride] = None,
        request_timeout: Optional[float] = None,
    ) -> SubscribeResult:
        call = SubscribeRequest(
            user=user,
            channel=channel,
            info=info,
            b64info=b64info,
            client=client,
            session=session,
            data=data,
            b64data=b64data,
            recover_since=recover_since,
            override=override,
        )
        return await self(call, request_timeout=request_timeout)

    async def unsubscribe(
        self,
        user: str,
        channel: str,
        client: Optional[str] = None,
        session: Optional[str] = None,
        request_timeout: Optional[float] = None,
    ) -> UnsubscribeResult:
        call = UnsubscribeRequest(
            user=user,
            channel=channel,
            client=client,
            session=session,
        )
        return await self(call, request_timeout=request_timeout)

    async def presence(
        self,
        channel: str,
        request_timeout: Optional[float] = None,
    ) -> PresenceResult:
        call = PresenceRequest(
            channel=channel,
        )
        return await self(call, request_timeout=request_timeout)

    async def presence_stats(
        self,
        channel: str,
        request_timeout: Optional[float] = None,
    ) -> PresenceStatsResult:
        call = PresenceStatsRequest(
            channel=channel,
        )
        return await self(call, request_timeout=request_timeout)

    async def history(
        self,
        channel: str,
        limit: Optional[int] = None,
        since: Optional[StreamPosition] = None,
        reverse: Optional[bool] = None,
        request_timeout: Optional[float] = None,
    ) -> HistoryResult:
        call = HistoryRequest(
            channel=channel,
            limit=limit,
            since=since,
            reverse=reverse,
        )
        return await self(call, request_timeout=request_timeout)

    async def history_remove(
        self,
        channel: str,
        request_timeout: Optional[float] = None,
    ) -> HistoryRemoveResult:
        call = HistoryRemoveRequest(
            channel=channel,
        )
        return await self(call, request_timeout=request_timeout)

    async def refresh(
        self,
        user: str,
        client: Optional[str] = None,
        session: Optional[str] = None,
        expire_at: Optional[int] = None,
        expired: Optional[bool] = None,
        request_timeout: Optional[float] = None,
    ) -> RefreshResult:
        call = RefreshRequest(
            user=user,
            client=client,
            session=session,
            expire_at=expire_at,
            expired=expired,
        )
        return await self(call, request_timeout=request_timeout)

    async def channels(
        self,
        pattern: Optional[str] = None,
        request_timeout: Optional[float] = None,
    ) -> ChannelsResult:
        call = ChannelsRequest(
            pattern=pattern,
        )
        return await self(call, request_timeout=request_timeout)

    async def disconnect(
        self,
        user: str,
        client: Optional[str] = None,
        session: Optional[str] = None,
        whitelist: Optional[List[str]] = None,
        disconnect: Optional[Disconnect] = None,
        request_timeout: Optional[float] = None,
    ) -> DisconnectResult:
        call = DisconnectRequest(
            user=user,
            client=client,
            session=session,
            whitelist=whitelist,
            disconnect=disconnect,
        )
        return await self(call, request_timeout=request_timeout)

    async def info(
        self,
        request_timeout: Optional[float] = None,
    ) -> InfoResult:
        call = InfoRequest()
        return await self(call, request_timeout=request_timeout)

    async def batch(
        self,
        commands: List[CentRequest[Any]],
        request_timeout: Optional[float] = None,
    ) -> BatchResult:
        call = BatchRequest.model_construct(commands=commands)
        return await self(call, request_timeout=request_timeout)

    async def __call__(self, method: CentRequest[T], request_timeout: Optional[float] = None) -> T:
        """
        Call API method

        :param method: Centrifugo method
        :return: Centrifugo response
        """
        return await self.session(self, method, timeout=request_timeout)
