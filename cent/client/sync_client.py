from typing import List, Optional, Any, Dict, TypeVar

from requests import Session

from cent.client.session import RequestsSession
from cent.dto import (
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
    BatchRequest,
    BatchResult,
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


class Client:
    def __init__(
        self,
        api_url: str,
        api_key: str,
        timeout: Optional[float] = 10.0,
        session: Optional[Session] = None,
    ) -> None:
        """
        :param api_url: Centrifugo API URL
        :param api_key: Centrifugo API key
        :param timeout: Base timeout for all requests.
        :param session: Custom `requests` session.
        """

        self._api_url = api_url
        self._api_key = api_key
        self._session = RequestsSession(
            api_url,
            timeout=timeout,
            session=session,
        )

    def publish(
        self,
        channel: str,
        data: Any,
        skip_history: Optional[bool] = None,
        tags: Optional[Dict[str, str]] = None,
        b64data: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> PublishResult:
        call = PublishRequest(
            channel=channel,
            data=data,
            skip_history=skip_history,
            tags=tags,
            b64data=b64data,
            idempotency_key=idempotency_key,
        )
        return self(call, timeout=timeout)

    def broadcast(
        self,
        channels: List[str],
        data: Any,
        skip_history: Optional[bool] = None,
        tags: Optional[Dict[str, str]] = None,
        b64data: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> BroadcastResult:
        call = BroadcastRequest(
            channels=channels,
            data=data,
            skip_history=skip_history,
            tags=tags,
            b64data=b64data,
            idempotency_key=idempotency_key,
        )
        return self(call, timeout=timeout)

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
        timeout: Optional[float] = None,
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
        return self(call, timeout=timeout)

    def unsubscribe(
        self,
        user: str,
        channel: str,
        client: Optional[str] = None,
        session: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> UnsubscribeResult:
        call = UnsubscribeRequest(
            user=user,
            channel=channel,
            client=client,
            session=session,
        )
        return self(call, timeout=timeout)

    def presence(
        self,
        channel: str,
        timeout: Optional[float] = None,
    ) -> PresenceResult:
        call = PresenceRequest(
            channel=channel,
        )
        return self(call, timeout=timeout)

    def presence_stats(
        self,
        channel: str,
        timeout: Optional[float] = None,
    ) -> PresenceStatsResult:
        call = PresenceStatsRequest(
            channel=channel,
        )
        return self(call, timeout=timeout)

    def history(
        self,
        channel: str,
        limit: Optional[int] = None,
        since: Optional[StreamPosition] = None,
        reverse: Optional[bool] = None,
        timeout: Optional[float] = None,
    ) -> HistoryResult:
        call = HistoryRequest(
            channel=channel,
            limit=limit,
            since=since,
            reverse=reverse,
        )
        return self(call, timeout=timeout)

    def history_remove(
        self,
        channel: str,
        timeout: Optional[float] = None,
    ) -> HistoryRemoveResult:
        call = HistoryRemoveRequest(
            channel=channel,
        )
        return self(call, timeout=timeout)

    def refresh(
        self,
        user: str,
        client: Optional[str] = None,
        session: Optional[str] = None,
        expired: Optional[bool] = None,
        expire_at: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> RefreshResult:
        call = RefreshRequest(
            user=user,
            client=client,
            session=session,
            expired=expired,
            expire_at=expire_at,
        )
        return self(call, timeout=timeout)

    def channels(
        self,
        pattern: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> ChannelsResult:
        call = ChannelsRequest(
            pattern=pattern,
        )
        return self(call, timeout=timeout)

    def disconnect(
        self,
        user: str,
        client: Optional[str] = None,
        session: Optional[str] = None,
        whitelist: Optional[List[str]] = None,
        disconnect: Optional[Disconnect] = None,
        timeout: Optional[float] = None,
    ) -> DisconnectResult:
        call = DisconnectRequest(
            user=user,
            client=client,
            session=session,
            whitelist=whitelist,
            disconnect=disconnect,
        )
        return self(call, timeout=timeout)

    def info(
        self,
        timeout: Optional[float] = None,
    ) -> InfoResult:
        call = InfoRequest()
        return self(call, timeout=timeout)

    def batch(
        self,
        commands: List[CentRequest[Any]],
        parallel: Optional[bool] = False,
        timeout: Optional[float] = None,
    ) -> BatchResult:
        call = BatchRequest.model_construct(commands=commands, parallel=parallel)
        return self(call, timeout=timeout)

    def close(self) -> None:
        self._session.close()

    def __call__(self, request: CentRequest[T], timeout: Optional[float] = None) -> T:
        """
        Call API method

        :param request: Centrifugo request
        :return: Centrifugo response
        """
        return self._session(self._api_key, request, timeout=timeout)

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, *kwargs: Any) -> None:
        self.close()
