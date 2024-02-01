from typing import Any

from cent.types.base import CentResult


class PublicationResult(CentResult):
    """Publication result."""

    data: Any
    """Custom JSON inside publication."""
    offset: int
    """Offset of publication in history stream."""
