from cent.methods.base import CentMethod, CentType


class CentError(Exception):
    """
    Wrapper for all exceptions coming from this library.
    """


class ClientDecodeError(CentError):
    """
    ClientDecodeError raised when response from Centrifugo can't be decoded
    from JSON.
    """


class InvalidApiKeyError(CentError):
    """
    InvalidApiKeyError raised when Centrifugo returns 401 status code.
    """


class DetailedAPIError(CentError):
    """
    DetailedAPIError raised when response from Centrifugo contains any error
    as a result of API command execution.
    """

    def __init__(self, method: CentMethod[CentType], code: int, message: str) -> None:
        self.method = method
        self.code = code
        self.message = message

    def __str__(self) -> str:
        return f"Centrifuge error #{self.code}: {self.message}"

    def __repr__(self) -> str:
        return f"{type(self).__name__}('{self}')"
