from typing import Optional, Dict, Any

import requests
from requests import Session

from cent.client.session.base_http_sync import BaseHttpSyncSession
from cent.exceptions import CentNetworkError, CentTimeoutError


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
        self._session: Session
        if session:
            self._session = session
        else:
            self._session = Session()

    def close(self) -> None:
        if self._session is not None:
            self._session.close()

    def make_request(
        self,
        api_key: str,
        method: str,
        json_data: Dict[str, Any],
        timeout: Optional[float] = None,
    ) -> str:
        if api_key:
            self._session.headers["X-API-Key"] = api_key

        url = f"{self._base_url}/{method}"

        try:
            raw_result = self._session.post(
                url=url,
                json=json_data,
                timeout=timeout or self._timeout,
            )
        except requests.exceptions.Timeout as error:
            raise CentTimeoutError(
                message="Request timeout",
            ) from error
        except requests.exceptions.ConnectionError as error:
            raise CentNetworkError(
                message=f"{type(error).__name__}: {error}",
            ) from error
        self.check_status_code(
            status_code=raw_result.status_code,
        )
        return raw_result.text

    def __del__(self) -> None:
        self.close()
