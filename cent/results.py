from typing import List, Any, Optional, Dict

from pydantic import Field

from cent.base import BaseResult
from cent.base import Response
from cent.types import Publication, Node, ClientInfo


class BatchResult(BaseResult):
    """Batch response."""

    replies: List[Any]
    """List of results from batch request."""


class PublishResult(BaseResult):
    """Publish result."""

    offset: Optional[int] = None
    """Offset of publication in history stream."""
    epoch: Optional[str] = None
    """Epoch of current stream."""


class BroadcastResult(BaseResult):
    """Publish result."""

    responses: List[Response[PublishResult]] = Field(default_factory=list)
    """Responses for each individual publish (with possible error and publish result)."""


class ChannelInfoResult(BaseResult):
    """Channel info result."""

    num_clients: int = Field(default=0)
    """Total number of connections currently subscribed to a channel."""


class ChannelsResult(BaseResult):
    """Channels result."""

    channels: Dict[str, ChannelInfoResult]
    """Map where key is channel and value is ChannelInfoResult."""


class DisconnectResult(BaseResult):
    """Disconnect result."""


class HistoryRemoveResult(BaseResult):
    """History remove result."""


class HistoryResult(BaseResult):
    """History result."""

    publications: List[Publication] = Field(default_factory=list)
    """List of publications in channel."""
    offset: Optional[int] = None
    """Top offset in history stream."""
    epoch: Optional[str] = None
    """Epoch of current stream."""


class InfoResult(BaseResult):
    """Info result."""

    nodes: List[Node]
    """Information about all nodes in a cluster."""


class PresenceResult(BaseResult):
    """Presence result."""

    presence: Dict[str, ClientInfo]
    """Offset of publication in history stream."""


class PresenceStatsResult(BaseResult):
    """Presence stats result."""

    num_clients: int = Field(default=0)
    """Total number of clients in channel."""
    num_users: int = Field(default=0)
    """Total number of unique users in channel."""


class RefreshResult(BaseResult):
    """Refresh result."""


class SubscribeResult(BaseResult):
    """Subscribe result."""


class UnsubscribeResult(BaseResult):
    """Unsubscribe result."""
