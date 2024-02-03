from cent.protos.centrifugal.centrifugo.api import InfoRequest as GrpcInfoRequest
from cent.methods import CentRequest
from cent.types.info_result import InfoResult


class InfoRequest(CentRequest[InfoResult]):
    """Info request."""

    __returning__ = InfoResult
    __api_method__ = "info"

    __grpc_method__ = GrpcInfoRequest
