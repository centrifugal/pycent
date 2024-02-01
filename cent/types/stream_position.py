from pydantic import BaseModel


class StreamPosition(BaseModel):
    """Stream position."""

    offset: int
    """Offset of publication in history stream."""
    epoch: str
    """Epoch of current stream."""
