from typing import Any

from pydantic import Field

from cent.types.base import CentResult


class PublicationResult(CentResult):
    """Publication result."""

    data: Any
    """Custom JSON inside publication."""
    offset: int = Field(default=0)
    """Offset of publication in history stream."""
