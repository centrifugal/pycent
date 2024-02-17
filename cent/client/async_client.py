from typing import Optional, Any, cast

from aiohttp import ClientSession

from cent.client.session import AiohttpSession
from cent.dto import CentRequest, CentResultType


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

    async def send(
        self,
        request: CentRequest[CentResultType],
        timeout: Optional[float] = None,
    ) -> CentResultType:
        method = request.get_api_method()
        payload = request.to_json()
        content = await self._session.make_request(
            self._api_key,
            method,
            payload,
            timeout=timeout,
        )
        response = request.parse_response(content)
        return cast(CentResultType, response.result)

    async def close(self) -> None:
        await self._session.close()

    async def __aenter__(self) -> "AsyncClient":
        return self

    async def __aexit__(self, *kwargs: Any) -> None:
        await self.close()
