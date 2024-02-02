from cent.centrifugal.centrifugo.api import Disconnect as GrpcDisconnect

from cent.methods.base import NestedModel


class Disconnect(NestedModel):
    """Disconnect data."""

    __grpc_method__ = GrpcDisconnect

    code: int
    """Disconnect code."""
    reason: str
    """Disconnect reason."""
