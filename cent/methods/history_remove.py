from cent.protos.centrifugal.centrifugo.api import HistoryRemoveRequest as GrpcHistoryRemoveRequest
from cent.methods import CentRequest
from cent.types.history_remove_result import HistoryRemoveResult


class HistoryRemoveRequest(CentRequest[HistoryRemoveResult]):
    """History remove request."""

    __returning__ = HistoryRemoveResult
    __api_method__ = "history_remove"

    __grpc_method__ = GrpcHistoryRemoveRequest

    channel: str
    """Name of channel to remove history."""
