from typing import List, Optional, Any, Dict, TypeVar

from cent.client.session import BaseSyncSession, RequestsSession
from cent.methods import (
    CentMethod,
    BroadcastMethod,
    PublishMethod,
    SubscribeMethod,
)
from cent.types import (
    StreamPosition,
    PublishObject,
    BroadcastObject,
    Override,
    SubscribeObject,
)

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
        data: Dict[str, Any],
        skip_history: Optional[bool] = None,
        tags: Optional[Dict[str, str]] = None,
        b64data: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        request_timeout: Optional[int] = None,
    ) -> PublishObject:
        call = PublishMethod(
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
        data: Dict[str, Any],
        skip_history: Optional[bool] = None,
        tags: Optional[Dict[str, str]] = None,
        b64data: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        request_timeout: Optional[int] = None,
    ) -> BroadcastObject:
        call = BroadcastMethod(
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
        info: Optional[Dict[Any, Any]] = None,
        b64info: Optional[str] = None,
        client: Optional[str] = None,
        session: Optional[str] = None,
        data: Optional[Dict[Any, Any]] = None,
        b64data: Optional[str] = None,
        recover_since: Optional[StreamPosition] = None,
        override: Optional[Override] = None,
        request_timeout: Optional[int] = None,
    ) -> SubscribeObject:
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
        return self(call, request_timeout=request_timeout)

    def __call__(
        self, method: CentMethod[T], request_timeout: Optional[int] = None
    ) -> T:
        """
        Call API method

        :param method: Centrifugo method
        :return: Centrifugo response
        """
        return self.session(self, method, timeout=request_timeout)
