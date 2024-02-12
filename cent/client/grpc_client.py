from typing import Optional, Dict, TypeVar, List, Any

from cent.client.session import GrpcSession
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
)
from cent.types import (
    StreamPosition,
    ChannelOptionsOverride,
    Disconnect,
)


T = TypeVar("T")


class GrpcClient:
    def __init__(
        self,
        host: str,
        port: int,
        request_timeout: Optional[float] = 10.0,
    ) -> None:
        """
        Initialize GRPC client.

        :param host: Centrifugo host.
        :param port: Centrifugo port.
        :param request_timeout: Request timeout.
        """
        self._session = GrpcSession(host, port, timeout=request_timeout)

    async def publish(
        self,
        channel: str,
        data: bytes,
        skip_history: Optional[bool] = None,
        tags: Optional[Dict[str, str]] = None,
        idempotency_key: Optional[str] = None,
        request_timeout: Optional[float] = None,
    ) -> PublishResult:
        call = PublishRequest(
            channel=channel,
            data=data,
            skip_history=skip_history,
            tags=tags,
            idempotency_key=idempotency_key,
        )
        return await self(call, request_timeout=request_timeout)

    async def broadcast(
        self,
        channels: List[str],
        data: bytes,
        skip_history: Optional[bool] = None,
        tags: Optional[Dict[str, str]] = None,
        idempotency_key: Optional[str] = None,
        request_timeout: Optional[float] = None,
    ) -> BroadcastResult:
        call = BroadcastRequest(
            channels=channels,
            data=data,
            skip_history=skip_history,
            tags=tags,
            idempotency_key=idempotency_key,
        )
        return await self(call, request_timeout=request_timeout)

    async def subscribe(
        self,
        user: str,
        channel: str,
        info: Optional[bytes] = None,
        client: Optional[str] = None,
        session: Optional[str] = None,
        data: Optional[bytes] = None,
        recover_since: Optional[StreamPosition] = None,
        override: Optional[ChannelOptionsOverride] = None,
        request_timeout: Optional[float] = None,
    ) -> SubscribeResult:
        call = SubscribeRequest(
            user=user,
            channel=channel,
            info=info,
            client=client,
            session=session,
            data=data,
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

    async def close(self) -> None:
        self._session.close()

    async def __call__(
        self, request: CentRequest[T], request_timeout: Optional[float] = None
    ) -> T:
        """
        Call API method

        :param request: Centrifugo request
        :return: Centrifugo response
        """
        return await self._session(request, request_timeout)

    async def __aenter__(self) -> "GrpcClient":
        return self

    async def __aexit__(self, *kwargs: Any) -> None:
        await self.close()
