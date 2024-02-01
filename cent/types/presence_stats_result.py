from cent.types.base import CentResult


class PresenceStatsResult(CentResult):
    """Presence stats result."""

    num_clients: int
    """Total number of clients in channel."""
    num_users: int
    """Total number of unique users in channel."""
