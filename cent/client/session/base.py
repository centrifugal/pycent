from http import HTTPStatus
from typing import Final, TYPE_CHECKING, Callable, Any, Union, Dict, List

from aiohttp.http import SERVER_SOFTWARE
from pydantic import ValidationError, TypeAdapter, __version__

from cent.exceptions import (
    CentClientDecodeError,
    CentAPIError,
    CentUnauthorizedError,
    CentTransportError,
)
from cent.methods.base import (
    json_loads as _json_loads,
    CentRequest,
    CentType,
    Response,
)
from cent.methods.batch import BatchRequest

if TYPE_CHECKING:
    from cent.client.sync_client import Client
    from cent.client.async_client import AsyncClient

DEFAULT_TIMEOUT: Final[float] = 10.0
_JsonLoads = Callable[..., Any]
_JsonDumps = Callable[..., str]


class BaseSession:
    """Base class for all sessions."""

    def __init__(
        self,
        base_url: str,
        json_loads: _JsonLoads = _json_loads,
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
        self._headers = {
            "User-Agent": f"{SERVER_SOFTWARE} pycent/{__version__}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def get_batch_json_data(method: BatchRequest) -> Dict[str, List[Dict[str, Any]]]:
        commands = [
            {command.__api_method__: command.model_dump(exclude_none=True)}
            for command in method.commands
        ]
        return {"commands": commands}

    @staticmethod
    def validate_batch(
        client: Union["Client", "AsyncClient"],
        method: BatchRequest,
        json_replies: List[Dict[str, Any]],
    ) -> Dict[str, Dict[str, List[Any]]]:
        """Validate batch method."""
        replies: List[CentRequest[Any]] = []
        for command_method, json_data in zip(method.commands, json_replies):
            validated_method: CentRequest[Any] = TypeAdapter(
                command_method.__returning__
            ).validate_python(
                json_data[command_method.__api_method__],
                context={"client": client},
            )
            replies.append(validated_method)
        return {"result": {"replies": replies}}

    def check_response(
        self,
        client: Union["Client", "AsyncClient"],
        method: CentRequest[CentType],
        status_code: int,
        content: str,
    ) -> Response[CentType]:
        """Validate response."""
        if status_code == HTTPStatus.UNAUTHORIZED:
            raise CentUnauthorizedError

        if status_code != HTTPStatus.OK:
            raise CentTransportError(
                method=method,
                status_code=status_code,
            )

        try:
            json_data = self.json_loads(content)
        except Exception as err:
            raise CentClientDecodeError from err

        if isinstance(method, BatchRequest):
            json_data = self.validate_batch(client, method, json_data["replies"])

        try:
            response_type = Response[method.__returning__]  # type: ignore
            response = TypeAdapter(response_type).validate_python(
                json_data,
                context={"client": client},
            )
        except ValidationError as err:
            raise CentClientDecodeError from err

        if response.error:
            raise CentAPIError(
                method=method,
                code=response.error.code,
                message=response.error.message,
            )

        return response
