from typing import List, Optional

from pydantic import Field

from cent.types.base import CentResult
from cent.types.publication_result import PublicationResult


class HistoryResult(CentResult):
    """History result."""

    publications: List[PublicationResult] = Field(default_factory=list)
    """List of publications in channel."""
    offset: Optional[int] = None
    """Top offset in history stream."""
    epoch: Optional[str] = None
    """Epoch of current stream."""
