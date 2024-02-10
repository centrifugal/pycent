from pydantic import Field

from cent.types.base import CentResult


class PresenceStatsResult(CentResult):
    """Presence stats result."""

    num_clients: int = Field(default=0)
    """Total number of clients in channel."""
    num_users: int = Field(default=0)
    """Total number of unique users in channel."""
