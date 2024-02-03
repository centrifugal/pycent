from typing import List, Optional, Any, Dict, TypeVar

from cent.client.session import BaseSyncSession, RequestsSession
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


class Client:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        session: Optional[BaseSyncSession] = None,
    ) -> None:
        """
        :param base_url: Centrifuge base_url
        :param api_key: Centrifuge API key
        :param session: Custom Session instance
        """

        self._base_url = base_url
        self.api_key = api_key
        self.session = session or RequestsSession(base_url=base_url)

    def publish(
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
        return self(call, request_timeout=request_timeout)

    def broadcast(
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
        return self(call, request_timeout=request_timeout)

    def subscribe(
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
        return self(call, request_timeout=request_timeout)

    def unsubscribe(
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
        return self(call, request_timeout=request_timeout)

    def presence(
        self,
        channel: str,
        request_timeout: Optional[float] = None,
    ) -> PresenceResult:
        call = PresenceRequest(
            channel=channel,
        )
        return self(call, request_timeout=request_timeout)

    def presence_stats(
        self,
        channel: str,
        request_timeout: Optional[float] = None,
    ) -> PresenceStatsResult:
        call = PresenceStatsRequest(
            channel=channel,
        )
        return self(call, request_timeout=request_timeout)

    def history(
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
        return self(call, request_timeout=request_timeout)

    def history_remove(
        self,
        channel: str,
        request_timeout: Optional[float] = None,
    ) -> HistoryRemoveResult:
        call = HistoryRemoveRequest(
            channel=channel,
        )
        return self(call, request_timeout=request_timeout)

    def refresh(
        self,
        user: str,
        client: Optional[str] = None,
        session: Optional[str] = None,
        expired: Optional[bool] = None,
        expire_at: Optional[int] = None,
        request_timeout: Optional[float] = None,
    ) -> RefreshResult:
        call = RefreshRequest(
            user=user,
            client=client,
            session=session,
            expired=expired,
            expire_at=expire_at,
        )
        return self(call, request_timeout=request_timeout)

    def channels(
        self,
        pattern: Optional[str] = None,
        request_timeout: Optional[float] = None,
    ) -> ChannelsResult:
        call = ChannelsRequest(
            pattern=pattern,
        )
        return self(call, request_timeout=request_timeout)

    def disconnect(
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
        return self(call, request_timeout=request_timeout)

    def info(
        self,
        request_timeout: Optional[float] = None,
    ) -> InfoResult:
        call = InfoRequest()
        return self(call, request_timeout=request_timeout)

    def batch(
        self,
        commands: List[CentRequest[Any]],
        request_timeout: Optional[float] = None,
    ) -> BatchResult:
        call = BatchRequest.model_construct(commands=commands)
        return self(call, request_timeout=request_timeout)

    def __call__(self, method: CentRequest[T], request_timeout: Optional[float] = None) -> T:
        """
        Call API method

        :param method: Centrifugo method
        :return: Centrifugo response
        """
        return self.session(self, method, timeout=request_timeout)
