from cent.types.base import CentResult


class ProcessResult(CentResult):
    """Process result."""

    cpu: float
    """Process CPU usage."""
    rss: int
    """Process RSS."""
