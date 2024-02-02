from typing import Optional

from cent.centrifugal.centrifugo.api import ChannelsRequest as GrpcChannelsRequest
from cent.methods import CentMethod
from cent.types.channels_result import ChannelsResult


class ChannelsMethod(CentMethod[ChannelsResult]):
    """Channels request."""

    __returning__ = ChannelsResult
    __api_method__ = "channels"

    __grpc_method__ = GrpcChannelsRequest

    pattern: Optional[str] = None
    """Pattern to filter channels, we are using https://github.com/gobwas/glob library for matching."""
