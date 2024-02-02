from typing import Dict

from pydantic import Field

from cent.types.base import CentResult


class MetricsResult(CentResult):
    """Metrics result."""

    interval: float = Field(default=0.0)
    """Interval."""
    items: Dict[str, float]
    """Map where key is string and value is float."""
