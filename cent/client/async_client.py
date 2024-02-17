from typing import Optional, Any, TypeVar

from aiohttp import ClientSession

from cent.client.session import AiohttpSession
from cent.dto import CentRequest


T = TypeVar("T")


class AsyncClient:
    def __init__(
        self,
        api_url: str,
        api_key: str,
        timeout: Optional[float] = 10.0,
        session: Optional[ClientSession] = None,
    ) -> None:
        """
        :param api_url: Centrifugo API URL
        :param api_key: Centrifugo API key
        :param timeout: Base timeout for all requests
        :param session: Custom `aiohttp` session
        """
        self._api_key = api_key
        self._session = AiohttpSession(
            api_url,
            timeout=timeout,
            session=session,
        )

    async def send(self, request: CentRequest[T], timeout: Optional[float] = None) -> T:
        return await self._session(self._api_key, request, timeout=timeout)

    async def close(self) -> None:
        await self._session.close()

    async def __aenter__(self) -> "AsyncClient":
        return self

    async def __aexit__(self, *kwargs: Any) -> None:
        await self.close()
