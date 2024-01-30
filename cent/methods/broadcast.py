from typing import Any, Dict, Optional, List

from cent.methods.base import CentMethod
from cent.types.broadcast import BroadcastObject


class BroadcastMethod(CentMethod[BroadcastObject]):
    """Broadcast request."""

    __returning__ = BroadcastObject
    __api_method__ = "broadcast"

    channels: List[str]
    """List of channels to publish data to."""
    data: Dict[Any, Any]
    """Custom JSON data to publish into a channel."""
    skip_history: Optional[bool] = None
    """Skip adding publications to channels' history for this request."""
    tags: Optional[Dict[str, str]] = None
    """Publication tags - map with arbitrary string keys and values which is attached to publication and will be delivered to clients."""
    b64data: Optional[str] = None
    """Custom binary data to publish into a channel encoded to base64 so it's possible to use HTTP API to send binary to clients. Centrifugo will decode it from base64 before publishing. In case of GRPC you can publish binary using data field."""
    idempotency_key: Optional[str] = None
    """Optional idempotency key to drop duplicate publications upon retries. It acts per channel. Centrifugo currently keeps the cache of idempotent publish results during 5 minutes window. Available since Centrifugo v5.2.0"""
