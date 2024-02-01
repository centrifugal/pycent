from typing import List, Any

from cent.types import CentResult


class BatchResult(CentResult):
    """Batch response."""

    replies: List[Any]
    """List of results from batch request."""
