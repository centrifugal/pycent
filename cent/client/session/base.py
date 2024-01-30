import json
from abc import ABC, abstractmethod
from types import TracebackType
from typing import Final, TYPE_CHECKING, Callable, Any, Optional, cast, Type

from pydantic import ValidationError

from cent.exceptions import ClientDecodeError, DetailedAPIError
from cent.methods.base import CentMethod, CentType, Response

if TYPE_CHECKING:
    from cent.client.cent_client import CentClient

DEFAULT_TIMEOUT: Final[float] = 60.0
_JsonLoads = Callable[..., Any]
_JsonDumps = Callable[..., str]


class BaseSession(ABC):
    """Base class for all sessions."""

    def __init__(
        self,
        base_url: str,
        json_loads: _JsonLoads = json.loads,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        """
        Initialize session.

        :param base_url: Centrifuge base url.
        :param json_loads: JSON loader.
        :param timeout: Default request timeout.
        """
        self._base_url = base_url
        self.json_loads = json_loads
        self._timeout = timeout

    def check_response(
        self,
        client: "CentClient",
        method: CentMethod[CentType],
        content: str,
    ) -> Response[CentType]:
        """Validate response."""
        try:
            json_data = self.json_loads(content)
        except Exception as err:
            raise ClientDecodeError from err

        try:
            response_type = Response[method.__returning__]  # type: ignore
            response = response_type.model_validate(
                json_data,
                context={"client": client},
            )
        except ValidationError as err:
            raise ClientDecodeError from err

        if response.error is None:
            return response

        raise DetailedAPIError(
            method=method,
            code=response.error.code,
            message=response.error.message,
        )

    @abstractmethod
    async def close(self) -> None:  # pragma: no cover
        """
        Close client session
        """

    @abstractmethod
    async def make_request(
        self,
        client: "CentClient",
        method: CentMethod[CentType],
        timeout: Optional[float] = None,
    ) -> CentType:  # pragma: no cover
        """
        Make request to centrifuge API.

        :param client: Centrifuge client.
        :param method: Centrifuge method.
        :param timeout: Request timeout.
        """
        ...

    async def __call__(
        self,
        client: "CentClient",
        method: CentMethod[CentType],
        timeout: Optional[float] = None,
    ) -> CentType:
        return cast(CentType, await self.make_request(client, method, timeout))

    async def __aenter__(self) -> "BaseSession":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        await self.close()
