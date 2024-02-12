from typing import Optional, cast

import requests
from requests import Session

from cent.base import CentType, CentRequest
from cent.client.session.base_http_sync import BaseHttpSyncSession
from cent.exceptions import CentNetworkError, CentTimeoutError
from cent.requests import BatchRequest


class RequestsSession(BaseHttpSyncSession):
    def __init__(
        self,
        base_url: str,
        timeout: Optional[float] = 10.0,
        session: Optional[Session] = None,
    ) -> None:
        super().__init__()
        self._base_url = base_url
        self._timeout = timeout
        self._headers = {
            "User-Agent": "centrifugal/pycent",
            "Content-Type": "application/json",
        }
        self._session: Session
        if session:
            self._session = session
        else:
            self._session = Session()
            self._session.headers.update(self._headers)

    def close(self) -> None:
        if self._session is not None:
            self._session.close()

    def make_request(
        self,
        api_key: str,
        request: CentRequest[CentType],
        timeout: Optional[float] = None,
    ) -> CentType:
        self._session.headers["X-API-Key"] = api_key
        if isinstance(request, BatchRequest):
            json_data = self.get_batch_json_data(request)
        else:
            json_data = request.model_dump(exclude_none=True)

        url = f"{self._base_url}/{request.__api_method__}"

        try:
            raw_result = self._session.post(
                url=url,
                json=json_data,
                timeout=timeout or self._timeout,
            )
        except requests.exceptions.Timeout as error:
            raise CentTimeoutError(
                request=request,
                message="Request timeout",
            ) from error
        except requests.exceptions.ConnectionError as error:
            raise CentNetworkError(
                request=request,
                message=f"{type(error).__name__}: {error}",
            ) from error
        response = self.check_response(
            request=request,
            status_code=raw_result.status_code,
            content=raw_result.text,
        )
        return cast(CentType, response.result)

    def __del__(self) -> None:
        self.close()
