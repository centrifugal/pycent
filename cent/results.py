from typing import List, Any, Optional, Dict

from pydantic import Field

from cent.base import CentResult
from cent.base import Response
from cent.types import Publication, Node, ClientInfo


class BatchResult(CentResult):
    """Batch response.

    Attributes:
        replies: List of results from batch request.
    """

    replies: List[Any]


class PublishResult(CentResult):
    """Publish result.

    Attributes:
        offset: Offset of publication in history stream.
        epoch: Epoch of current stream.
    """

    offset: Optional[int] = None
    epoch: Optional[str] = None


class BroadcastResult(CentResult):
    """Broadcast result.

    Attributes:
        responses: List of responses for each individual publish
        (with possible error and publish result)
    """

    responses: List[Response[PublishResult]] = Field(default_factory=list)


class ChannelInfoResult(CentResult):
    """Channel info result.

    Attributes:
        num_clients: Total number of connections currently subscribed to a channel.
    """

    num_clients: int = Field(default=0)


class ChannelsResult(CentResult):
    """Channels result.

    Attributes:
        channels: Map where key is channel and value is ChannelInfoResult.
    """

    channels: Dict[str, ChannelInfoResult]


class DisconnectResult(CentResult):
    """Disconnect result."""


class HistoryRemoveResult(CentResult):
    """History remove result."""


class HistoryResult(CentResult):
    """History result.

    Attributes:
        publications: List of publications in channel.
        offset: Top offset in history stream.
        epoch: Epoch of current stream.
    """

    publications: List[Publication] = Field(default_factory=list)
    offset: Optional[int] = None
    epoch: Optional[str] = None


class InfoResult(CentResult):
    """Info result.

    Attributes:
        nodes: Information about all nodes in a cluster.
    """

    nodes: List[Node]


class PresenceResult(CentResult):
    """Presence result.

    Attributes:
        presence: Map where key is client ID and value is ClientInfo.
    """

    presence: Dict[str, ClientInfo]


class PresenceStatsResult(CentResult):
    """Presence stats result.

    Attributes:
        num_clients: Total number of clients in channel.
        num_users: Total number of unique users in channel.
    """

    num_clients: int = Field(default=0)
    num_users: int = Field(default=0)


class RefreshResult(CentResult):
    """Refresh result."""


class SubscribeResult(CentResult):
    """Subscribe result."""


class UnsubscribeResult(CentResult):
    """Unsubscribe result."""
