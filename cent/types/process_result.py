from pydantic import Field

from cent.types.base import CentResult


class ProcessResult(CentResult):
    """Process result."""

    cpu: float = Field(default=0.0)
    """Process CPU usage."""
    rss: int
    """Process RSS."""
