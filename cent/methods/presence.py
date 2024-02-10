from cent.protos.centrifugal.centrifugo.api import (
    PresenceRequest as GrpcPresenceRequest,
    PresenceResult as GrpcPresenceResult,
)
from cent.methods import CentRequest
from cent.types.presence_result import PresenceResult


class PresenceRequest(CentRequest[PresenceResult]):
    """Presence request."""

    __returning__ = PresenceResult
    __api_method__ = "presence"

    __grpc_returning__ = GrpcPresenceResult
    __grpc_method__ = GrpcPresenceRequest

    channel: str
    """Name of channel to call presence from."""
