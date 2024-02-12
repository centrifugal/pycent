import asyncio
from typing import Optional, cast

from aiohttp import ClientSession, ClientError, ClientTimeout

from cent.client.session.base_http_async import BaseHttpAsyncSession
from cent.base import CentType, CentRequest
from cent.requests import BatchRequest
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
            self._session = ClientSession(
                headers={
                    "User-Agent": "centrifugal/pycent",
                    "Content-Type": "application/json",
                },
                timeout=ClientTimeout(total=self._timeout),
            )

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()

            # https://docs.aiohttp.org/en/stable/client_advanced.html#graceful-shutdown
            await asyncio.sleep(0)

    async def make_request(
        self,
        api_key: str,
        request: CentRequest[CentType],
        timeout: Optional[float] = None,
    ) -> CentType:
        session = self._session
        if api_key:
            session.headers["X-API-Key"] = api_key

        if isinstance(request, BatchRequest):
            json_data = self.get_batch_json_data(request)
        else:
            json_data = request.model_dump(exclude_none=True)

        url = f"{self._base_url}/{request.__api_method__}"

        try:
            async with session.post(
                url=url,
                json=json_data,
                timeout=timeout or self._timeout,
            ) as resp:
                raw_result = await resp.text()
        except asyncio.TimeoutError as error:
            raise CentTimeoutError(
                request=request,
                message="Request timeout",
            ) from error
        except ClientError as error:
            raise CentNetworkError(
                request=request,
                message=f"{type(error).__name__}: {error}",
            ) from error
        response = self.check_response(
            request=request,
            status_code=resp.status,
            content=raw_result,
        )
        return cast(CentType, response.result)

    def __del__(self) -> None:
        if self._session and not self._session.closed:
            if self._session.connector is not None and self._session.connector_owner:
                self._session.connector.close()
            self._session._connector = None
