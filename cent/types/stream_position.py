from cent.types.base import CentResult


class StreamPosition(CentResult):
    """Stream position."""

    offset: int
    """Offset of publication in history stream."""
    epoch: str
    """Epoch of current stream."""
