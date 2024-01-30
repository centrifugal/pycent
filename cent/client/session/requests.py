from typing import Optional, TYPE_CHECKING, cast, Any

from aiohttp.hdrs import USER_AGENT, CONTENT_TYPE
from aiohttp.http import SERVER_SOFTWARE
from requests import Session

from cent.__meta__ import __version__
from cent.methods.base import CentMethod, CentType
from cent.client.session.base_sync import BaseSyncSession

if TYPE_CHECKING:
    from cent.client.client import Client


class RequestsSession(BaseSyncSession):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._session = Session()
        self._session.headers.update(
            {
                USER_AGENT: f"{SERVER_SOFTWARE} pycent/{__version__}",
                CONTENT_TYPE: "application/json",
                "X-Centrifugo-Error-Mode": "transport",
            }
        )

    def close(self) -> None:
        if self._session is not None:
            self._session.close()

    def make_request(
        self,
        client: "Client",
        method: CentMethod[CentType],
        timeout: Optional[float] = None,
    ) -> CentType:
        self._session.headers["X-API-Key"] = client.api_key
        json_data = method.model_dump(exclude_none=True)

        url = f"{self._base_url}/{method.__api_method__}"

        raw_result = self._session.post(
            url=url,
            json=json_data,
            timeout=timeout or self._timeout,
        )
        response = self.check_response(
            client=client,
            method=method,
            status_code=raw_result.status_code,
            content=raw_result.text,
        )
        return cast(CentType, response.result)

    def __del__(self) -> None:
        self.close()
