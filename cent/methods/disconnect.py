from typing import Optional, List

from cent.centrifugal.centrifugo.api import DisconnectRequest as GrpcDisconnectRequest
from cent.methods import CentMethod
from cent.types import Disconnect
from cent.types.disconnect_result import DisconnectResult


class DisconnectMethod(CentMethod[DisconnectResult]):
    """Disconnect request."""

    __returning__ = DisconnectResult
    __api_method__ = "disconnect"

    __grpc_method__ = GrpcDisconnectRequest

    user: str
    """User ID to disconnect."""
    client: Optional[str] = None
    """Specific client ID to disconnect (user still required to be set)."""
    session: Optional[str] = None
    """Specific client session to disconnect (user still required to be set)."""
    whitelist: Optional[List[str]] = None
    """Array of client IDs to keep."""
    disconnect: Optional[Disconnect] = None
    """Provide custom disconnect object, see below."""
