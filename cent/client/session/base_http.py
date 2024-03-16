from http import HTTPStatus

from cent.exceptions import (
    CentUnauthorizedError,
    CentTransportError,
)


class BaseHttpSession:
    """Base class for HTTP sessions."""

    @staticmethod
    def check_status_code(
        status_code: int,
    ) -> None:
        if status_code == HTTPStatus.UNAUTHORIZED:
            raise CentUnauthorizedError

        if status_code != HTTPStatus.OK:
            raise CentTransportError(
                status_code=status_code,
            )
