from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Optional, cast

from cent.client.session.base import BaseSession
from cent.methods.base import CentMethod, CentType

if TYPE_CHECKING:
    from cent.client.async_client import AsyncClient


class BaseAsyncSession(BaseSession, ABC):
    """Base class for all sessions."""

    @abstractmethod
    async def close(self) -> None:
        """
        Close client session
        """

    @abstractmethod
    async def make_request(
        self,
        client: "AsyncClient",
        method: CentMethod[CentType],
        timeout: Optional[float] = None,
    ) -> CentType:
        """
        Make request to centrifuge API.

        :param client: Centrifuge client.
        :param method: Centrifuge method.
        :param timeout: Request timeout.
        """

    async def __call__(
        self,
        client: "AsyncClient",
        method: CentMethod[CentType],
        timeout: Optional[float] = None,
    ) -> CentType:
        return cast(CentType, await self.make_request(client, method, timeout))

    async def __aenter__(self) -> "BaseAsyncSession":
        return self

    async def __aexit__(self, *kwargs: Any) -> None:
        await self.close()
