from typing import Optional

from cent.centrifugal.centrifugo.api import RefreshRequest as GrpcRefreshRequest
from cent.methods import CentMethod
from cent.types.refresh_result import RefreshResult


class RefreshMethod(CentMethod[RefreshResult]):
    """Refresh request."""

    __returning__ = RefreshResult
    __api_method__ = "refresh"

    __grpc_method__ = GrpcRefreshRequest

    user: str
    """User ID to refresh."""
    client: Optional[str] = None
    """Client ID to refresh (user still required to be set)."""
    session: Optional[str] = None
    """Specific client session to refresh (user still required to be set)."""
    expired: Optional[bool] = None
    """Mark connection as expired and close with Disconnect Expired reason."""
    expire_at: Optional[int] = None
    """Unix time (in seconds) in the future when the connection will expire."""
