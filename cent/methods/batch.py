from typing import List, Any

from cent.centrifugal.centrifugo.api import BatchRequest as GrpcBatchRequest
from cent.methods import CentMethod
from cent.types.batch_result import BatchResult


class BatchMethod(CentMethod[BatchResult]):
    """Batch request."""

    __returning__ = BatchResult
    __api_method__ = "batch"

    __grpc_method__ = GrpcBatchRequest

    commands: List[CentMethod[Any]]
    """List of commands to execute in batch."""
