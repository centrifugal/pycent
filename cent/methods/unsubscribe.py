from typing import Optional

from cent.centrifugal.centrifugo.api import UnsubscribeRequest as GrpcUnsubscribeRequest
from cent.methods.base import CentMethod
from cent.types.unsubscribe_result import UnsubscribeResult


class UnsubscribeMethod(CentMethod[UnsubscribeResult]):
    """Unsubscribe request."""

    __returning__ = UnsubscribeResult
    __api_method__ = "unsubscribe"

    __grpc_method__ = GrpcUnsubscribeRequest

    user: str
    """User ID to unsubscribe."""
    channel: str
    """Name of channel to unsubscribe user to."""
    client: Optional[str] = None
    """Specific client ID to unsubscribe (user still required to be set)."""
    session: Optional[str] = None
    """Specific client session to disconnect (user still required to be set)."""
