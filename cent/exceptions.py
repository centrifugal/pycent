from cent.base import CentType, CentRequest


class CentError(Exception):
    """
    Wrapper for all exceptions coming from this library.
    """


class CentNetworkError(CentError):
    """CentNetworkError raised when Centrifugo is not available."""

    def __init__(self, method: CentRequest[CentType], message: str) -> None:
        self.method = method
        self.message = message

    def __str__(self) -> str:
        return f"HTTP error - {self.message}"

    def __repr__(self) -> str:
        return f"{type(self).__name__}('{self}')"


class CentClientDecodeError(CentError):
    """
    CentClientDecodeError raised when response from Centrifugo can't be decoded
    from JSON.
    """


class CentUnauthorizedError(CentError):
    """
    CentUnauthorizedError raised when Centrifugo returns 401 status code.
    """


class CentAPIError(CentError):
    """
    CentAPIError raised when response from Centrifugo contains any error
    as a result of API command execution.
    """

    def __init__(self, method: CentRequest[CentType], code: int, message: str) -> None:
        self.method = method
        self.code = code
        self.message = message

    def __str__(self) -> str:
        return f"Centrifuge error #{self.code}: {self.message}"

    def __repr__(self) -> str:
        return f"{type(self).__name__}('{self}')"


class CentTransportError(CentError):
    """CentTransportError raised when returns non-200 status code."""

    def __init__(self, method: CentRequest[CentType], status_code: int):
        self.method = method
        self.status_code = status_code

    def __str__(self) -> str:
        return f"Transport error - {self.status_code}"

    def __repr__(self) -> str:
        return f"{type(self).__name__}('{self}')"
