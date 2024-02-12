from abc import ABC, abstractmethod
from typing import Any, Optional, cast

from cent.client.session.base_http import BaseHttpSession
from cent.base import CentType, CentRequest


class BaseHttpAsyncSession(BaseHttpSession, ABC):
    """Base class for all sessions."""

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
        return cast(CentType, await self.make_request(api_key, request, timeout))

    async def __aenter__(self) -> "BaseHttpAsyncSession":
        return self

    async def __aexit__(self, *kwargs: Any) -> None:
        await self.close()