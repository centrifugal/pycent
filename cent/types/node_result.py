from typing import Optional

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
    num_clients: int
    """Total number of connections."""
    num_users: int
    """Total number of users."""
    num_channels: int
    """Total number of channels."""
    uptime: int
    """Node uptime."""
    metrics: Optional[MetricsResult] = None
    """Node metrics."""
    process: Optional[ProcessResult] = None
    """Node process."""
    num_subs: int
    """Total number of subscriptions."""
