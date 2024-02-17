class CentError(Exception):
    """
    Wrapper for all exceptions coming from this library.
    """


class CentNetworkError(CentError):
    """CentNetworkError raised when Centrifugo is unreachable or not available."""

    def __init__(self, message: str) -> None:
        self.message = message

    def __str__(self) -> str:
        return f"Network error - {self.message}"

    def __repr__(self) -> str:
        return f"{type(self).__name__}('{self}')"


class CentTransportError(CentError):
    """CentTransportError raised when HTTP request results into non-200 status code."""

    def __init__(self, status_code: int):
        self.status_code = status_code

    def __str__(self) -> str:
        return f"Transport error - {self.status_code}"

    def __repr__(self) -> str:
        return f"{type(self).__name__}('{self}')"


class CentTimeoutError(CentError):
    """CentTimeoutError raised when request is timed out"""

    def __init__(self, message: str) -> None:
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


class CentApiResponseError(CentError):
    """
    CentApiResponseError raised when the response from Centrifugo server API contains
    any error as a result of API command execution.
    """

    def __init__(self, code: int, message: str) -> None:
        self.code = code
        self.message = message

    def __str__(self) -> str:
        return f"Server API response error #{self.code}: {self.message}"

    def __repr__(self) -> str:
        return f"{type(self).__name__}('{self}')"
