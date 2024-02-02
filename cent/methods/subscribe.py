import json
from typing import Optional, Any

from pydantic import Field, field_serializer
from pydantic_core.core_schema import SerializationInfo

from cent.centrifugal.centrifugo.api import SubscribeRequest as GrpcSubscribeRequest
from cent.methods.base import CentMethod
from cent.types import (
    StreamPosition,
    SubscribeResult,
    ChannelOptionsOverride,
)


class SubscribeMethod(CentMethod[SubscribeResult]):
    """Subscribe request."""

    __returning__ = SubscribeResult
    __api_method__ = "subscribe"

    __grpc_method__ = GrpcSubscribeRequest

    user: str
    """User ID to subscribe."""
    channel: str
    """Name of channel to subscribe user to."""
    info: Optional[Any] = None
    """Attach custom data to subscription (will be used in presence and join/leave messages)."""
    b64info: Optional[str] = Field(None, alias="b64_info")
    """info in base64 for binary mode (will be decoded by Centrifugo)."""
    client: Optional[str] = None
    """Specific client ID to subscribe (user still required to be set, will ignore other user connections with different client IDs)."""
    session: Optional[str] = None
    """Specific client session to subscribe (user still required to be set)."""
    data: Optional[Any] = None
    """Custom subscription data (will be sent to client in Subscribe push)."""
    b64data: Optional[str] = Field(None, alias="b64_data")
    """Same as data but in base64 format (will be decoded by Centrifugo)."""
    recover_since: Optional[StreamPosition] = None
    """Stream position to recover from."""
    override: Optional[ChannelOptionsOverride] = None
    """Allows dynamically override some channel options defined in Centrifugo configuration (see below available fields)."""

    @field_serializer("data", when_used="unless-none")
    def grpc_serialize_data(self, data: Any, _info: SerializationInfo) -> Any:
        if _info.mode == "grpc":
            return json.dumps(data).encode()
        return data

    @field_serializer("info", when_used="unless-none")
    def grpc_serialize_info(self, info: Any, _info: SerializationInfo) -> Any:
        if _info.mode == "grpc":
            return json.dumps(info).encode()
        return info
