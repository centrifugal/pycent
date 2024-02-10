from typing import Dict

from cent.types.base import CentResult
from cent.types.channel_info_result import ChannelInfoResult


class ChannelsResult(CentResult):
    """Channels result."""

    channels: Dict[str, ChannelInfoResult]
    """Map where key is channel and value is ChannelInfoResult."""
