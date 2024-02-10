from typing import Any, Optional

from cent.types.base import CentResult


class ClientInfoResult(CentResult):
    """Client info result."""

    client: str
    """Client ID."""
    user: str
    """User ID."""
    conn_info: Optional[Any] = None
    """Optional connection info."""
    chan_info: Optional[Any] = None
    """Optional channel info."""
