from typing import Optional

from pydantic import Field

from cent.types.base import CentResult
from cent.types.metrics_result import MetricsResult
from cent.types.process_result import ProcessResult


class NodeResult(CentResult):
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
    metrics: Optional[MetricsResult] = None
    """Node metrics."""
    process: Optional[ProcessResult] = None
    """Node process."""
