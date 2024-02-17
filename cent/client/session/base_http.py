import json
from http import HTTPStatus
from typing import Any, Dict, List, cast

from pydantic import ValidationError, TypeAdapter

from cent.exceptions import (
    CentDecodeError,
    CentApiResponseError,
    CentUnauthorizedError,
    CentTransportError,
)
from cent.dto import (
    CentRequest,
    CentType,
    Response,
    BatchRequest,
)


class BaseHttpSession:
    """Base class for HTTP sessions."""

    @staticmethod
    def get_batch_json_data(request: BatchRequest) -> Dict[str, List[Dict[str, Any]]]:
        commands = [
            {command.__api_method__: command.model_dump(exclude_none=True)}
            for command in request.commands
        ]
        return {"commands": commands}

    @staticmethod
    def validate_batch(
        request: BatchRequest,
        json_replies: List[Dict[str, Any]],
    ) -> Dict[str, Dict[str, List[Any]]]:
        replies: List[CentRequest[Any]] = []
        for command_method, json_data in zip(request.commands, json_replies):
            validated_request: CentRequest[Any] = TypeAdapter(
                command_method.__returning__
            ).validate_python(
                json_data[command_method.__api_method__],
            )
            replies.append(validated_request)
        return {"result": {"replies": replies}}

    def check_response(
        self,
        request: CentRequest[CentType],
        status_code: int,
        content: str,
    ) -> CentType:
        if status_code == HTTPStatus.UNAUTHORIZED:
            raise CentUnauthorizedError

        if status_code != HTTPStatus.OK:
            raise CentTransportError(
                request=request,
                status_code=status_code,
            )

        try:
            json_data = json.loads(content)
        except Exception as err:
            raise CentDecodeError from err

        if isinstance(request, BatchRequest):
            json_data = self.validate_batch(request, json_data["replies"])

        try:
            response_type = Response[request.__returning__]  # type: ignore
            response = TypeAdapter(response_type).validate_python(
                json_data,
            )
        except ValidationError as err:
            raise CentDecodeError from err

        if response.error:
            raise CentApiResponseError(
                request=request,
                code=response.error.code,
                message=response.error.message,
            )

        return cast(CentType, response.result)
