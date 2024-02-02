from typing import Any, Optional, Dict, TypeVar, List

from cent.client.session.grpc import GrpcSession
from cent.methods import (
    CentMethod,
    BroadcastMethod,
    PublishMethod,
    SubscribeMethod,
    UnsubscribeMethod,
    PresenceMethod,
    PresenceStatsMethod,
    HistoryMethod,
    HistoryRemoveMethod,
    RefreshMethod,
    ChannelsMethod,
    DisconnectMethod,
    InfoMethod,
)
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

T = TypeVar("T")


class GrpcClient:
    def __init__(self, host: str, port: int) -> None:
        self.session = GrpcSession(host=host, port=port)

    async def publish(
        self,
        channel: str,
        data: Any,
        skip_history: Optional[bool] = None,
        tags: Optional[Dict[str, str]] = None,
        b64data: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> PublishResult:
        call = PublishMethod(
            channel=channel,
            data=data,
            skip_history=skip_history,
            tags=tags,
            b64data=b64data,
            idempotency_key=idempotency_key,
        )
        return await self(call)

    async def broadcast(
        self,
        channels: List[str],
        data: Any,
        skip_history: Optional[bool] = None,
        tags: Optional[Dict[str, str]] = None,
        b64data: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> BroadcastResult:
        call = BroadcastMethod(
            channels=channels,
            data=data,
            skip_history=skip_history,
            tags=tags,
            b64data=b64data,
            idempotency_key=idempotency_key,
        )
        return await self(call)

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
    ) -> SubscribeResult:
        call = SubscribeMethod(
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
        return await self(call)

    async def unsubscribe(
        self,
        user: str,
        channel: str,
        client: Optional[str] = None,
        session: Optional[str] = None,
    ) -> UnsubscribeResult:
        call = UnsubscribeMethod(
            user=user,
            channel=channel,
            client=client,
            session=session,
        )
        return await self(call)

    async def presence(
        self,
        channel: str,
    ) -> PresenceResult:
        call = PresenceMethod(
            channel=channel,
        )
        return await self(call)

    async def presence_stats(
        self,
        channel: str,
    ) -> PresenceStatsResult:
        call = PresenceStatsMethod(
            channel=channel,
        )
        return await self(call)

    async def history(
        self,
        channel: str,
        limit: Optional[int] = None,
        since: Optional[StreamPosition] = None,
        reverse: Optional[bool] = None,
    ) -> HistoryResult:
        call = HistoryMethod(
            channel=channel,
            limit=limit,
            since=since,
            reverse=reverse,
        )
        return await self(call)

    async def history_remove(
        self,
        channel: str,
    ) -> HistoryRemoveResult:
        call = HistoryRemoveMethod(
            channel=channel,
        )
        return await self(call)

    async def refresh(
        self,
        user: str,
        client: Optional[str] = None,
        session: Optional[str] = None,
        expire_at: Optional[int] = None,
        expired: Optional[bool] = None,
    ) -> RefreshResult:
        call = RefreshMethod(
            user=user,
            client=client,
            session=session,
            expire_at=expire_at,
            expired=expired,
        )
        return await self(call)

    async def channels(
        self,
        pattern: Optional[str] = None,
    ) -> ChannelsResult:
        call = ChannelsMethod(
            pattern=pattern,
        )
        return await self(call)

    async def disconnect(
        self,
        user: str,
        client: Optional[str] = None,
        session: Optional[str] = None,
        whitelist: Optional[List[str]] = None,
        disconnect: Optional[Disconnect] = None,
    ) -> DisconnectResult:
        call = DisconnectMethod(
            user=user,
            client=client,
            session=session,
            whitelist=whitelist,
            disconnect=disconnect,
        )
        return await self(call)

    async def info(
        self,
    ) -> InfoResult:
        call = InfoMethod()
        return await self(call)

    async def __call__(self, method: CentMethod[T]) -> T:
        """
        Call API method

        :param method: Centrifugo method
        :return: Centrifugo response
        """
        return await self.session(self, method)
