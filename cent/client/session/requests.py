from typing import Optional, TYPE_CHECKING, cast, Any

import requests
from requests import Session

from cent.methods.base import CentRequest, CentType
from cent.client.session.base_sync import BaseSyncSession
from cent.exceptions import CentNetworkError
from cent.methods.batch import BatchRequest

if TYPE_CHECKING:
    from cent.client.sync_client import Client


class RequestsSession(BaseSyncSession):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._session = Session()
        self._session.headers.update(self._headers)

    def close(self) -> None:
        if self._session is not None:
            self._session.close()

    def make_request(
        self,
        client: "Client",
        method: CentRequest[CentType],
        timeout: Optional[float] = None,
    ) -> CentType:
        self._session.headers["X-API-Key"] = client.api_key
        if isinstance(method, BatchRequest):
            json_data = self.get_batch_json_data(method)
        else:
            json_data = method.model_dump(exclude_none=True)

        url = f"{self._base_url}/{method.__api_method__}"

        try:
            raw_result = self._session.post(
                url=url,
                json=json_data,
                timeout=timeout or self._timeout,
            )
        except requests.exceptions.Timeout as error:
            raise CentNetworkError(
                method=method,
                message="Request timeout",
            ) from error
        except requests.exceptions.ConnectionError as error:
            raise CentNetworkError(
                method=method,
                message=f"{type(error).__name__}: {error}",
            ) from error
        response = self.check_response(
            client=client,
            method=method,
            status_code=raw_result.status_code,
            content=raw_result.text,
        )
        return cast(CentType, response.result)

    def __del__(self) -> None:
        self.close()
