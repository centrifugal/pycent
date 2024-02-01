from typing import Optional, List

from cent.methods import CentMethod
from cent.types import Disconnect
from cent.types.disconnect_result import DisconnectResult


class DisconnectMethod(CentMethod[DisconnectResult]):
    """Disconnect request."""

    __returning__ = DisconnectResult
    __api_method__ = "disconnect"

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
