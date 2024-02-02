from typing import Optional

from cent.centrifugal.centrifugo.api import HistoryRequest as GrpcHistoryRequest
from cent.methods import CentMethod
from cent.types import StreamPosition
from cent.types.history_result import HistoryResult


class HistoryMethod(CentMethod[HistoryResult]):
    """History request."""

    __returning__ = HistoryResult
    __api_method__ = "history"

    __grpc_method__ = GrpcHistoryRequest

    channel: str
    """Name of channel to call history from."""
    limit: Optional[int] = None
    """Limit number of returned publications, if not set in request then only current stream position information will present in result (without any publications)."""
    since: Optional[StreamPosition] = None
    """To return publications after this position."""
    reverse: Optional[bool] = None
    """Iterate in reversed order (from latest to earliest)."""
