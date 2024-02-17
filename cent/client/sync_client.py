from typing import Optional, Any, TypeVar

from requests import Session

from cent.client.session import RequestsSession
from cent.dto import CentRequest

T = TypeVar("T")


class Client:
    def __init__(
        self,
        api_url: str,
        api_key: str,
        timeout: Optional[float] = 10.0,
        session: Optional[Session] = None,
    ) -> None:
        """
        :param api_url: Centrifugo API URL
        :param api_key: Centrifugo API key
        :param timeout: Base timeout for all requests.
        :param session: Custom `requests` session.
        """

        self._api_url = api_url
        self._api_key = api_key
        self._session = RequestsSession(
            api_url,
            timeout=timeout,
            session=session,
        )

    def send(self, request: CentRequest[T], timeout: Optional[float] = None) -> T:
        return self._session(self._api_key, request, timeout=timeout)

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, *kwargs: Any) -> None:
        self.close()
