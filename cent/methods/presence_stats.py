from cent.methods import CentMethod
from cent.types.presence_stats_result import PresenceStatsResult


class PresenceStatsMethod(CentMethod[PresenceStatsResult]):
    """Presence request."""

    __returning__ = PresenceStatsResult
    __api_method__ = "presence_stats"

    channel: str
    """Name of channel to call presence from."""
