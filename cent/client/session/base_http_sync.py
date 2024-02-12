from abc import abstractmethod, ABC
from typing import Optional

from cent.client.session.base_http import BaseHttpSession
from cent.base import CentType, CentRequest


class BaseHttpSyncSession(BaseHttpSession, ABC):
    """Base class for all sessions."""

    @abstractmethod
    def close(self) -> None:
        """
        Close client session
        """

    @abstractmethod
    def make_request(
        self,
        api_key: str,
        request: CentRequest[CentType],
        timeout: Optional[float] = None,
    ) -> CentType:
        """
        Make request to Centrifugo API.

        :param api_key: Centrifugo API key.
        :param request: Centrifugo API request.
        :param timeout: Request timeout.
        """

    def __call__(
        self,
        api_key: str,
        request: CentRequest[CentType],
        timeout: Optional[float] = None,
    ) -> CentType:
        return self.make_request(api_key, request, timeout)
