from cent.methods import CentMethod
from cent.types.presence_result import PresenceResult


class PresenceMethod(CentMethod[PresenceResult]):
    """Presence request."""

    __returning__ = PresenceResult
    __api_method__ = "presence"

    channel: str
    """Name of channel to call presence from."""
