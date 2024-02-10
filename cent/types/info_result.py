from typing import List

from cent.types.base import CentResult
from cent.types.node_result import NodeResult


class InfoResult(CentResult):
    """Info result."""

    nodes: List[NodeResult]
    """Information about all nodes in a cluster."""
