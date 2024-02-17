import asyncio
from typing import Optional, Dict, Any

from aiohttp import ClientSession, ClientError

from cent.client.session.base_http_async import BaseHttpAsyncSession
from cent.exceptions import CentNetworkError, CentTimeoutError


class AiohttpSession(BaseHttpAsyncSession):
    def __init__(
        self,
        base_url: str,
        timeout: Optional[float] = 10.0,
        session: Optional[ClientSession] = None,
    ) -> None:
        super().__init__()
        self._base_url = base_url
        self._timeout = timeout
        self._session: ClientSession
        if session:
            self._session = session
        else:
            self._session = ClientSession()

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()

            # https://docs.aiohttp.org/en/stable/client_advanced.html#graceful-shutdown
            await asyncio.sleep(0)

    async def make_request(
        self,
        api_key: str,
        method: str,
        json_data: Dict[str, Any],
        timeout: Optional[float] = None,
    ) -> str:
        session = self._session
        if api_key:
            session.headers["X-API-Key"] = api_key

        url = f"{self._base_url}/{method}"

        try:
            async with session.post(
                url=url,
                json=json_data,
                timeout=timeout or self._timeout,
            ) as resp:
                raw_result = await resp.text()
        except asyncio.TimeoutError as error:
            raise CentTimeoutError(
                message="Request timeout",
            ) from error
        except ClientError as error:
            raise CentNetworkError(
                message=f"{type(error).__name__}: {error}",
            ) from error
        self.check_status_code(status_code=resp.status)
        return raw_result

    def __del__(self) -> None:
        if self._session and not self._session.closed:
            if self._session.connector is not None and self._session.connector_owner:
                self._session.connector.close()
            self._session._connector = None
