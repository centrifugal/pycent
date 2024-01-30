from cent.types.base import CentObject


class StreamPosition(CentObject):
    """Stream position."""

    offset: int
    """Offset of publication in history stream."""
    epoch: str
    """Epoch of current stream."""
