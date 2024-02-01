from abc import abstractmethod, ABC
from typing import Final, TYPE_CHECKING, Callable, Any, Optional

from cent.methods.base import CentMethod, CentType
from cent.client.session.base import BaseSession

if TYPE_CHECKING:
    from cent.client.sync_client import Client

DEFAULT_TIMEOUT: Final[float] = 60.0
_JsonLoads = Callable[..., Any]
_JsonDumps = Callable[..., str]


class BaseSyncSession(BaseSession, ABC):
    """Base class for all sessions."""

    @abstractmethod
    def close(self) -> None:
        """
        Close client session
        """

    @abstractmethod
    def make_request(
        self,
        client: "Client",
        method: CentMethod[CentType],
        timeout: Optional[float] = None,
    ) -> CentType:
        """
        Make request to centrifuge API.

        :param client: Centrifuge client.
        :param method: Centrifuge method.
        :param timeout: Request timeout.
        """
        ...

    def __call__(
        self,
        client: "Client",
        method: CentMethod[CentType],
        timeout: Optional[float] = None,
    ) -> CentType:
        return self.make_request(client, method, timeout)
