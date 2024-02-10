from typing import Optional, Any, Dict

from pydantic import Field

from cent.base import BaseResult, NestedModel
from cent.proto.centrifugal.centrifugo.api import (
    SubscribeOptionOverride as GrpcChannelOptionOverride,
    BoolValue as GrpcBoolValue,
    StreamPosition as GrpcStreamPosition,
    Disconnect as GrpcDisconnect,
)


class BoolValue(NestedModel):
    """Bool value."""

    __grpc_method__ = GrpcBoolValue

    value: bool


class StreamPosition(NestedModel):
    """
    Stream position representation.

    Attributes:
        offset (int): Offset of publication in history stream.
        epoch (str): Epoch of current stream.
    """

    __grpc_method__ = GrpcStreamPosition

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

    __grpc_method__ = GrpcChannelOptionOverride

    presence: Optional[BoolValue] = None
    join_leave: Optional[BoolValue] = None
    force_push_join_leave: Optional[BoolValue] = None
    force_positioning: Optional[BoolValue] = None
    force_recovery: Optional[BoolValue] = None


class ProcessStats(BaseResult):
    """
    Represents statistics of a process.

    Attributes:
        cpu (float): Process CPU usage as a percentage. Defaults to 0.0.
        rss (int): Process Resident Set Size (RSS) in bytes.
    """

    cpu: float = Field(default=0.0)
    rss: int


class ClientInfo(BaseResult):
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


class Publication(BaseResult):
    """Publication result."""

    data: Any
    """Custom JSON inside publication."""
    offset: int = Field(default=0)
    """Offset of publication in history stream."""


class Metrics(BaseResult):
    """Metrics result."""

    interval: float = Field(default=0.0)
    """Interval."""
    items: Dict[str, float]
    """Map where key is string and value is float."""


class Node(BaseResult):
    """Node result."""

    uid: str
    """Node unique identifier."""
    name: str
    """Node name."""
    version: str
    """Node version."""
    num_clients: int = Field(default=0)
    """Total number of connections."""
    num_subs: int = Field(default=0)
    """Total number of subscriptions."""
    num_users: int = Field(default=0)
    """Total number of users."""
    num_channels: int = Field(default=0)
    """Total number of channels."""
    uptime: int = Field(default=0)
    """Node uptime."""
    metrics: Optional[Metrics] = None
    """Node metrics."""
    process: Optional[ProcessStats] = None
    """Node process."""


class Disconnect(NestedModel):
    """Disconnect data."""

    __grpc_method__ = GrpcDisconnect

    code: int
    """Disconnect code."""
    reason: str
    """Disconnect reason."""
