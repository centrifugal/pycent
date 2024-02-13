from typing import Optional, Any, Dict

from pydantic import Field

from cent.base import CentResult, NestedModel


class Disconnect(NestedModel):
    """Disconnect data.

    Attributes:
        code (int): Disconnect code.
        reason (str): Disconnect reason.
    """

    code: int
    reason: str


class BoolValue(NestedModel):
    """Bool value.

    Attributes:
        value (bool): Value.
    """

    value: bool


class StreamPosition(NestedModel):
    """
    Stream position representation.

    Attributes:
        offset (int): Offset of publication in history stream.
        epoch (str): Epoch of current stream.
    """

    offset: int
    epoch: str


class ChannelOptionsOverride(NestedModel):
    """
    Override object for channel options.

    Attributes:
        presence (Optional[BoolValue]): Override for presence.
        join_leave (Optional[BoolValue]): Override for join_leave behavior.
        force_push_join_leave (Optional[BoolValue]): Force push for join_leave events.
        force_positioning (Optional[BoolValue]): Override for force positioning.
        force_recovery (Optional[BoolValue]): Override for force recovery.
    """

    presence: Optional[BoolValue] = None
    join_leave: Optional[BoolValue] = None
    force_push_join_leave: Optional[BoolValue] = None
    force_positioning: Optional[BoolValue] = None
    force_recovery: Optional[BoolValue] = None


class ProcessStats(CentResult):
    """
    Represents statistics of a process.

    Attributes:
        cpu (float): Process CPU usage as a percentage. Defaults to 0.0.
        rss (int): Process Resident Set Size (RSS) in bytes.
    """

    cpu: float = Field(default=0.0)
    rss: int


class ClientInfo(CentResult):
    """
    Represents the result containing client information.

    Attributes:
        client (str): Client ID.
        user (str): User ID.
        conn_info (Optional[Any]): Optional connection info. This can include details
            such as IP address, location, etc.
        chan_info (Optional[Any]): Optional channel info. This might include specific
            settings or preferences related to the channel.
    """

    client: str
    user: str
    conn_info: Optional[Any] = None
    chan_info: Optional[Any] = None


class Publication(CentResult):
    """Publication result.

    Attributes:
        offset (int): Offset of publication in history stream.
        data (Any): Custom JSON inside publication.
        tags (Optional[Dict[str, str]]): Tags are optional.
    """

    data: Any
    offset: int = Field(default=0)
    tags: Optional[Dict[str, str]] = None


class Metrics(CentResult):
    """Metrics result.

    Attributes:
        interval (float): Metrics aggregation interval.
        items (Dict[str, float]): metric values.
    """

    interval: float = Field(default=0.0)
    items: Dict[str, float]


class Node(CentResult):
    """Node result.

    Attributes:
        uid (str): Node unique identifier.
        name (str): Node name.
        version (str): Node version.
        num_clients (int): Total number of connections.
        num_subs (int): Total number of subscriptions.
        num_users (int): Total number of users.
        num_channels (int): Total number of channels.
        uptime (int): Node uptime.
        metrics (Optional[Metrics]): Node metrics.
        process (Optional[ProcessStats]): Node process stats.
    """

    uid: str
    name: str
    version: str
    num_clients: int = Field(default=0)
    num_subs: int = Field(default=0)
    num_users: int = Field(default=0)
    num_channels: int = Field(default=0)
    uptime: int = Field(default=0)
    metrics: Optional[Metrics] = None
    process: Optional[ProcessStats] = None
