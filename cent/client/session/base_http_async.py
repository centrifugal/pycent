from abc import ABC, abstractmethod
from typing import Optional

from cent.client.session.base_http import BaseHttpSession
from cent.dto import CentType, CentRequest


class BaseHttpAsyncSession(BaseHttpSession, ABC):
    @abstractmethod
    async def close(self) -> None:
        """
        Close client session
        """

    @abstractmethod
    async def make_request(
        self,
        api_key: str,
        request: CentRequest[CentType],
        timeout: Optional[float] = None,
    ) -> CentType:
        """
        Make request to centrifuge API.

        :param api_key: Centrifugo API key.
        :param request: Centrifugo API request.
        :param timeout: Request timeout.
        """

    async def __call__(
        self,
        api_key: str,
        request: CentRequest[CentType],
        timeout: Optional[float] = None,
    ) -> CentType:
        return await self.make_request(api_key, request, timeout)
