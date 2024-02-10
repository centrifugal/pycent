from pydantic import Field

from cent.types.base import CentResult


class ChannelInfoResult(CentResult):
    """Channel info result."""

    num_clients: int = Field(default=0)
    """Total number of connections currently subscribed to a channel."""
