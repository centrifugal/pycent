import json
from typing import Any, Dict, Optional

from cent.centrifugal.centrifugo.api import PublishRequest as GrpcPublishRequest
from pydantic import Field, field_serializer, SerializationInfo

from cent.methods.base import CentMethod
from cent.types.publish_result import PublishResult


class PublishMethod(CentMethod[PublishResult]):
    """Publish request."""

    __returning__ = PublishResult
    __api_method__ = "publish"

    __grpc_method__ = GrpcPublishRequest

    channel: str
    """Name of channel to publish."""
    data: Any
    """Custom JSON data to publish into a channel."""
    skip_history: Optional[bool] = None
    """Skip adding publication to history for this request."""
    tags: Optional[Dict[str, str]] = None
    """Publication tags - map with arbitrary string keys and values which is attached to publication and will be delivered to clients."""
    b64data: Optional[str] = Field(None, alias="b64_data")
    """Custom binary data to publish into a channel encoded to base64 so it's possible to use HTTP API to send binary to clients. Centrifugo will decode it from base64 before publishing. In case of GRPC you can publish binary using data field."""
    idempotency_key: Optional[str] = None
    """Optional idempotency key to drop duplicate publications upon retries. It acts per channel. Centrifugo currently keeps the cache of idempotent publish results during 5 minutes window. Available since Centrifugo v5.2.0"""

    @field_serializer("data")
    def grpc_serialize_data(self, data: Any, _info: SerializationInfo) -> Any:
        if _info.mode == "grpc":
            return json.dumps(data).encode()
        return data
