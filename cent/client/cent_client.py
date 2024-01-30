from typing import List, Optional, Any, Dict, TypeVar

from cent.client.session import BaseSession, AiohttpSession
from cent.methods.base import CentMethod
from cent.methods.broadcast import BroadcastMethod
from cent.methods.publish import PublishMethod
from cent.types.broadcast import BroadcastObject
from cent.types.publish import PublishObject

T = TypeVar("T")


class CentClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        session: Optional[BaseSession] = None,
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
        return await self(call, request_timeout=request_timeout)

    async def broadcast(
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
        return await self(call, request_timeout=request_timeout)

    async def __call__(
        self, method: CentMethod[T], request_timeout: Optional[int] = None
    ) -> T:
        """
        Call API method

        :param method: Centrifugo method
        :return: Centrifugo response
        """
        return await self.session(self, method, timeout=request_timeout)
