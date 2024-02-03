from typing import List, Any

from cent.protos.centrifugal.centrifugo.api import BatchRequest as GrpcBatchRequest
from cent.methods import CentRequest
from cent.types.batch_result import BatchResult


class BatchRequest(CentRequest[BatchResult]):
    """Batch request."""

    __returning__ = BatchResult
    __api_method__ = "batch"

    __grpc_method__ = GrpcBatchRequest

    commands: List[CentRequest[Any]]
    """List of commands to execute in batch."""
