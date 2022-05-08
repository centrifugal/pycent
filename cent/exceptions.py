class CentException(Exception):
    """
    Wrapper for all exceptions coming from this library.
    """

    pass


class RequestException(CentException):
    """
    RequestException means that request to Centrifugo API failed in some way.
    This is just a wrapper over RequestException from requests library.
    """

    pass


class ClientNotEmpty(CentException):
    """
    ClientNotEmpty raised when attempting to call single method but internal
    client command buffer is not empty.
    """

    pass


class ResponseError(CentException):
    """
    Raised when response from Centrifugo contains any error as result of API
    command execution.
    """

    pass
