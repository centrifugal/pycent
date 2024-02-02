from cent.centrifugal.centrifugo.api import StreamPosition as GrpcStreamPosition
from cent.methods.base import NestedModel


class StreamPosition(NestedModel):
    """Stream position."""

    __grpc_method__ = GrpcStreamPosition

    offset: int
    """Offset of publication in history stream."""
    epoch: str
    """Epoch of current stream."""
