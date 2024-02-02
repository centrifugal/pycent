from typing import Optional

from cent.centrifugal.centrifugo.api import SubscribeOptionOverride as GrpcChannelOptionOverride
from cent.methods.base import NestedModel
from cent.methods.bool_value import BoolValue


class ChannelOptionsOverride(NestedModel):
    """Override object."""

    __grpc_method__ = GrpcChannelOptionOverride

    presence: Optional[BoolValue] = None
    """Override presence."""
    join_leave: Optional[BoolValue] = None
    """Override join_leave."""
    force_push_join_leave: Optional[BoolValue] = None
    """Override force_push_join_leave."""
    force_positioning: Optional[BoolValue] = None
    """Override force_positioning."""
    force_recovery: Optional[BoolValue] = None
    """Override force_recovery."""
