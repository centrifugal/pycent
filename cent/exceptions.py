from cent.methods.base import CentMethod, CentType


class CentError(Exception):
    """
    Wrapper for all exceptions coming from this library.
    """


class CentNetworkError(CentError):
    """CentNetworkError raised when Centrifugo is not available."""

    def __init__(self, method: CentMethod[CentType], message: str) -> None:
        self.method = method
        self.message = message

    def __str__(self) -> str:
        return f"HTTP error - {self.message}"

    def __repr__(self) -> str:
        return f"{type(self).__name__}('{self}')"


class ClientDecodeError(CentError):
    """
    ClientDecodeError raised when response from Centrifugo can't be decoded
    from JSON.
    """


class InvalidApiKeyError(CentError):
    """
    InvalidApiKeyError raised when Centrifugo returns 401 status code.
    """


class APIError(CentError):
    """
    APIError raised when response from Centrifugo contains any error
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


class TransportError(CentError):
    """TransportError raised when returns non-200 status code."""

    def __init__(self, method: CentMethod[CentType], status_code: int):
        self.method = method
        self.status_code = status_code

    def __str__(self) -> str:
        return f"Transport error - {self.status_code}"

    def __repr__(self) -> str:
        return f"{type(self).__name__}('{self}')"
