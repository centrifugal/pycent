from cent.centrifugal.centrifugo.api import InfoRequest as GrpcInfoRequest
from cent.methods import CentMethod
from cent.types.info_result import InfoResult


class InfoMethod(CentMethod[InfoResult]):
    """Info request."""

    __returning__ = InfoResult
    __api_method__ = "info"

    __grpc_method__ = GrpcInfoRequest
