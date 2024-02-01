from cent.types.base import CentResult


class ChannelInfoResult(CentResult):
    """Channel info result."""

    num_clients: int
    """Total number of connections currently subscribed to a channel."""
