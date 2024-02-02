from dataclasses import dataclass, asdict
from typing import TYPE_CHECKING, cast, Type, Dict, Any, List, Tuple

import betterproto
from grpclib import GRPCError
from grpclib.client import Channel
from pydantic import TypeAdapter, BaseModel

from cent.centrifugal.centrifugo.api import CentrifugoApiStub
from cent.exceptions import APIError, TransportError
from cent.methods.base import CentMethod, CentType, Response, Error

if TYPE_CHECKING:
    from cent.client.grpc_client import GrpcClient


@dataclass
class BaseResponse(betterproto.Message):
    error: Error
    result: Type[betterproto.Message]


def dict_factory(x: List[Tuple[str, Any]]) -> Dict[str, Any]:
    response = {}
    for k, v in x:
        if v:
            response[k] = v
    return response


class GrpcSession:
    def __init__(self, host: str, port: int) -> None:
        self._channel = Channel(host=host, port=port)
        self._stub = CentrifugoApiStub(channel=self._channel)

    def close(self) -> None:
        self._channel.close()

    @staticmethod
    def check_response(
        client: "GrpcClient",
        method: CentMethod[CentType],
        content: BaseResponse,
    ) -> None:
        """Validate response."""
        response_type = Response[method.__returning__]  # type: ignore
        response = TypeAdapter(response_type).validate_python(
            asdict(content, dict_factory=dict_factory), context={"client": client}
        )
        if response.error:
            raise APIError(
                method=method,
                code=response.error.code,
                message=response.error.message,
            )

    def convert_to_grpc(self, method: CentMethod[CentType]) -> Any:
        request = method.model_dump(by_alias=True, exclude_none=True, mode="grpc")
        for key, value in method.model_fields.items():
            attr = getattr(method, key)
            if issubclass(attr.__class__, BaseModel):
                request[value.alias or key] = self.convert_to_grpc(attr)
        return method.__grpc_method__(**request)

    async def make_request(
        self,
        client: "GrpcClient",
        method: CentMethod[CentType],
    ) -> None:
        api_method = getattr(self._stub, method.__api_method__)
        try:
            response = await api_method(self.convert_to_grpc(method))
        except GRPCError as error:
            raise TransportError(method=method, status_code=error.status.value) from None

        self.check_response(client, method, response)

    async def __call__(
        self,
        client: "GrpcClient",
        method: CentMethod[CentType],
    ) -> CentType:
        return cast(CentType, await self.make_request(client, method))

    def __del__(self) -> None:
        self.close()
