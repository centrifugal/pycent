from cent.methods import CentMethod
from cent.types.history_remove_result import HistoryRemoveResult


class HistoryRemoveMethod(CentMethod[HistoryRemoveResult]):
    """History remove request."""

    __returning__ = HistoryRemoveResult
    __api_method__ = "history_remove"

    channel: str
    """Name of channel to remove history."""
