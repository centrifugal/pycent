from typing import Dict

from cent.types.base import CentResult


class MetricsResult(CentResult):
    """Metrics result."""

    interval: float
    """Interval."""
    items: Dict[str, float]
    """Map where key is string and value is float."""
