from cent.protos.centrifugal.centrifugo.api import PresenceStatsRequest as GrpcPresenceStatsRequest
from cent.methods import CentRequest
from cent.types.presence_stats_result import PresenceStatsResult


class PresenceStatsRequest(CentRequest[PresenceStatsResult]):
    """Presence request."""

    __returning__ = PresenceStatsResult
    __api_method__ = "presence_stats"

    __grpc_method__ = GrpcPresenceStatsRequest

    channel: str
    """Name of channel to call presence from."""
