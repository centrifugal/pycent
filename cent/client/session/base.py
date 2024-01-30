import json
from http import HTTPStatus
from typing import Final, TYPE_CHECKING, Callable, Any, Union

from pydantic import ValidationError, TypeAdapter

from cent.exceptions import ClientDecodeError, DetailedAPIError, InvalidApiKeyError
from cent.methods.base import CentMethod, CentType, Response, Error

if TYPE_CHECKING:
    from cent.client.client import Client
    from cent.client.async_client import AsyncClient

DEFAULT_TIMEOUT: Final[float] = 10.0
_JsonLoads = Callable[..., Any]
_JsonDumps = Callable[..., str]


class BaseSession:
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
        client: Union["Client", "AsyncClient"],
        method: CentMethod[CentType],
        status_code: int,
        content: str,
    ) -> Response[CentType]:
        """Validate response."""
        if status_code == HTTPStatus.UNAUTHORIZED:
            raise InvalidApiKeyError

        try:
            json_data = self.json_loads(content)
        except Exception as err:
            raise ClientDecodeError from err

        if not (HTTPStatus.OK <= status_code <= HTTPStatus.IM_USED):
            error = Error.model_validate(json_data)
            raise DetailedAPIError(
                method=method,
                code=error.code,
                message=error.message,
            )

        try:
            response_type = Response[method.__returning__]  # type: ignore
            response = TypeAdapter(response_type).validate_python(
                json_data,
                context={"client": client},
            )
        except ValidationError as err:
            raise ClientDecodeError from err

        if response.error:
            raise DetailedAPIError(
                method=method,
                code=response.error.code,
                message=response.error.message,
            )

        return response
