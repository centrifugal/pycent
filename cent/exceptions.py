from cent.dto import CentType, CentRequest


class CentError(Exception):
    """
    Wrapper for all exceptions coming from this library.
    """


class CentNetworkError(CentError):
    """CentNetworkError raised when Centrifugo is unreachable or not available."""

    def __init__(self, request: CentRequest[CentType], message: str) -> None:
        self.request = request
        self.message = message

    def __str__(self) -> str:
        return f"Network error - {self.message}"

    def __repr__(self) -> str:
        return f"{type(self).__name__}('{self}')"


class CentTransportError(CentError):
    """CentTransportError raised when HTTP request results into non-200 status code."""

    def __init__(self, request: CentRequest[CentType], status_code: int):
        self.request = request
        self.status_code = status_code

    def __str__(self) -> str:
        return f"Transport error - {self.status_code}"

    def __repr__(self) -> str:
        return f"{type(self).__name__}('{self}')"


class CentTimeoutError(CentError):
    """CentTimeoutError raised when request is timed out"""

    def __init__(self, request: CentRequest[CentType], message: str) -> None:
        self.request = request
        self.message = message

    def __str__(self) -> str:
        return f"Timeout error - {self.message}"

    def __repr__(self) -> str:
        return f"{type(self).__name__}('{self}')"


class CentUnauthorizedError(CentError):
    """
    CentUnauthorizedError raised when Centrifugo returns 401 status code.
    """


class CentDecodeError(CentError):
    """
    CentDecodeError raised when response from Centrifugo can't be decoded.
    """


class CentResponseError(CentError):
    """
    CentAPIError raised when response from Centrifugo contains any error
    as a result of API command execution.
    """

    def __init__(self, request: CentRequest[CentType], code: int, message: str) -> None:
        self.request = request
        self.code = code
        self.message = message

    def __str__(self) -> str:
        return f"Server API response error #{self.code}: {self.message}"

    def __repr__(self) -> str:
        return f"{type(self).__name__}('{self}')"
