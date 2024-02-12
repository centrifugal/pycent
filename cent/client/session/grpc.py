from dataclasses import dataclass, asdict
from typing import cast, Type, Dict, Any, List, Tuple, Optional

import betterproto
from grpclib import GRPCError
from grpclib.client import Channel
from pydantic import TypeAdapter, BaseModel

from cent.proto.centrifugal.centrifugo.api import CentrifugoApiStub
from cent.exceptions import CentAPIError, CentTransportError, CentTimeoutError, CentNetworkError
from cent.base import CentType, Response, Error, CentRequest


@dataclass
class _BaseResponse(betterproto.Message):
    error: Error
    result: Type[betterproto.Message]


def _dict_factory(x: List[Tuple[str, Any]]) -> Dict[str, Any]:
    response = {}
    for k, v in x:
        if v:
            response[k] = v
    return response


class GrpcSession:
    def __init__(self, host: str, port: int, timeout: Optional[float] = 10.0) -> None:
        self._channel = Channel(host=host, port=port)
        self._stub = CentrifugoApiStub(channel=self._channel)
        self._timeout = timeout

    def close(self) -> None:
        self._channel.close()

    @staticmethod
    def check_response(
        request: CentRequest[CentType],
        content: _BaseResponse,
    ) -> Response[CentType]:
        """Validate response."""
        response_type = Response[request.__returning__]  # type: ignore
        response = TypeAdapter(response_type).validate_python(
            asdict(content, dict_factory=_dict_factory)
        )
        if response.error:
            raise CentAPIError(
                request=request,
                code=response.error.code,
                message=response.error.message,
            )
        return response

    def convert_to_grpc(self, request: CentRequest[CentType]) -> Any:
        request_dump = request.model_dump(by_alias=True, exclude_none=True, mode="grpc")
        for key, value in request.model_fields.items():
            attr = getattr(request, key)
            if issubclass(attr.__class__, BaseModel):
                request_dump[value.alias or key] = self.convert_to_grpc(attr)
        return request.__grpc_method__(**request_dump)

    async def make_request(
        self,
        request: CentRequest[CentType],
        timeout: Optional[float] = None,
    ) -> CentType:
        api_method = getattr(self._stub, request.__api_method__)
        try:
            response = await api_method(
                self.convert_to_grpc(request), timeout=timeout or self._timeout
            )
        except TimeoutError as error:
            raise CentTimeoutError(
                request=request,
                message="Request timeout",
            ) from error
        except GRPCError as error:
            raise CentTransportError(
                request=request,
                status_code=error.status.value,
            ) from error
        except Exception as error:
            raise CentNetworkError(
                request=request,
                message=f"{type(error).__name__}: {error}",
            ) from error

        resp = self.check_response(request, response)
        return cast(CentType, resp.result)

    async def __call__(
        self,
        request: CentRequest[CentType],
        timeout: Optional[float] = None,
    ) -> CentType:
        return cast(CentType, await self.make_request(request, timeout))

    def __del__(self) -> None:
        self.close()
