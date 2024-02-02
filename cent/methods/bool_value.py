from cent.centrifugal.centrifugo.api import BoolValue as GrpcBoolValue
from cent.methods.base import NestedModel


class BoolValue(NestedModel):
    """Bool value."""

    __grpc_method__ = GrpcBoolValue

    value: bool
    """Bool value."""
