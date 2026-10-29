"""The exceptions of cent, and retryable."""

from __future__ import annotations

import ssl
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from cent._batch import BatchResult
    from cent._broadcast import BroadcastResult, ChannelResult

# How many failures an aggregate error names in its message; all of them stay
# available in the error itself.
_MAX_ERROR_ITEMS = 3


class CentError(Exception):
    """The base of every exception cent raises.

    idempotency_key is set on the error broadcast_with_retry raises when no
    attempt got a reply - a timeout, say - to the key its attempts carried,
    made for the call when the request had none: Centrifugo may have
    published, and a retry with this key does not publish twice. It is None
    on other errors."""

    idempotency_key: str | None = None


class ApiError(CentError):
    """An error of Centrifugo itself: it understood the request and refused it,
    or failed to carry it out.

    Centrifugo identifies an error by its ``code``; ``message`` is for people
    and may change. Errors with a known code are raised as the subclass for
    it - ``except UnknownChannelError`` - and any other code as ApiError
    itself: Centrifugo adds codes from time to time, so match the ones you
    handle and treat the rest by their class.
    """

    CODE: ClassVar[int | None] = None

    code: int
    message: str
    temporary: bool

    def __init__(self, code: int, message: str = "", temporary: bool = False) -> None:
        super().__init__(code, message)
        self.code = code
        self.message = message
        # Set by Centrifugo when the same request may succeed if retried
        # later - a broker being unavailable, a rate limit - not because of
        # the request. It does not mean nothing was done: a publication may
        # have happened, so retry it with the same idempotency_key.
        # Centrifugo versions before the field existed never set it;
        # retryable takes that into account.
        self.temporary = temporary
        self._pro_method = ""

    def __str__(self) -> str:
        s = f"{self.message or 'server error'} (code {self.code})"
        if self._pro_method:
            s += f" ({self._pro_method} is a Centrifugo PRO method: is the server Centrifugo OSS?)"
        return s

    def __repr__(self) -> str:
        return f"{type(self).__name__}(code={self.code}, message={self.message!r}, temporary={self.temporary})"

    @staticmethod
    def from_wire(code: int, message: str = "", temporary: bool = False) -> ApiError:
        """The error for code: the subclass of a known code, ApiError otherwise."""
        cls = _BY_CODE.get(code, ApiError)
        return cls(code, message, temporary)


class InternalError(ApiError):
    """Code 100: an internal error of Centrifugo, temporary."""

    CODE = 100


class UnknownChannelError(ApiError):
    """Code 102: the channel is not in a namespace Centrifugo is configured with."""

    CODE = 102


class NotFoundError(ApiError):
    """Code 104: what the request refers to was not found.

    A method only Centrifugo PRO has, sent in a batch to Centrifugo OSS, fails
    with it too, instead of the 404 it gets when sent alone.
    """

    CODE = 104


class BadRequestError(ApiError):
    """Code 107: Centrifugo refused the request as invalid."""

    CODE = 107


class NotAvailableError(ApiError):
    """Code 108: the feature is not available - history or presence off in the
    channel's namespace, say."""

    CODE = 108


class TooManyRequestsError(ApiError):
    """Code 111: a rate limit was reached, temporary."""

    CODE = 111


class UnrecoverablePositionError(ApiError):
    """Code 112: the stream position asked for is not in the history any more."""

    CODE = 112


class ConflictError(ApiError):
    """Code 113: the request conflicts with the current state - a map publish
    whose version check failed, say."""

    CODE = 113


_BY_CODE: dict[int, type[ApiError]] = {
    cls.CODE: cls
    for cls in (
        InternalError,
        UnknownChannelError,
        NotFoundError,
        BadRequestError,
        NotAvailableError,
        TooManyRequestsError,
        UnrecoverablePositionError,
        ConflictError,
    )
    if cls.CODE is not None
}


class HTTPError(CentError):
    """A reply with an HTTP status other than 200: the request did not reach the
    API method. A 401 is an UnauthorizedError."""

    status_code: int
    body: bytes
    headers: Mapping[str, str]

    def __init__(self, status_code: int, body: bytes = b"", headers: Mapping[str, str] | None = None) -> None:
        super().__init__(status_code)
        self.status_code = status_code
        # The start of the reply's body, for diagnostics.
        self.body = body
        # The reply's headers: a request ID a proxy set, a Retry-After.
        self.headers = headers if headers is not None else {}
        self._pro_method = ""

    def __str__(self) -> str:
        s = f"unexpected HTTP status {self.status_code}"
        if 300 <= self.status_code < 400:
            # Centrifugo's API never redirects: something in front of it does,
            # which cent does not follow.
            s += " (a redirect, which cent does not follow: check api_endpoint, http or https say)"
        elif self.status_code == 404 and self._pro_method:
            s += (
                f" ({self._pro_method} is a Centrifugo PRO method: if other methods work, the server is Centrifugo OSS)"
            )
        elif self.status_code == 404:
            # The usual cause: api_endpoint lacks the API prefix.
            s += " (is api_endpoint the API base URL, such as http://localhost:8000/api?)"
        elif self.status_code == 401:
            s += " (check the credentials: api_key or bearer_token_func)"
        if self.body:
            s += ": " + self.body.decode("utf-8", "replace")
        return s

    def __repr__(self) -> str:
        return f"{type(self).__name__}(status_code={self.status_code})"


class UnauthorizedError(HTTPError):
    """A 401: Centrifugo did not accept the credentials - the API key or the
    bearer token."""


class DecodeError(CentError):
    """The reply is not a Centrifugo API reply. The usual cause is an
    api_endpoint which does not point at Centrifugo's API, so that something
    else - a proxy, a web page - answers instead."""


class InvalidRequestError(CentError, ValueError):
    """A request the client can tell is wrong without sending it: one which
    cannot be encoded - a payload which is not JSON, in any request - or a
    publication without a channel or data. It is never sent.

    Only rules which hold for every Centrifugo are checked; everything else
    Centrifugo checks itself, and reports as a BadRequestError.
    """


class InvalidConfigError(CentError, ValueError):
    """A client configuration with a mistake: the message names the option and
    the fix."""


class ClosedError(CentError):
    """A call made after the client was closed."""


class NetworkError(CentError):
    """The request failed on its way: a refused or reset connection, a failed
    TLS handshake. The cause is chained."""


class CentTimeoutError(CentError, TimeoutError):
    """The request timed out: its timeout, or request_timeout. Also a builtin
    TimeoutError, so ``except TimeoutError`` catches it whichever layer's
    clock ran out. A request which timed out may still have been carried out."""


class BatchNotSentError(CentError):
    """A pending command's result read before its batch was sent."""


class BatchSentError(CentError):
    """A batch sent again: a batch is sent once."""


class BroadcastFailedChannelsError(CentError):
    """A broadcast Centrifugo carried out which failed in one or more of its
    channels, up to all of them. ``result`` holds every channel's outcome.

    It is not an ApiError of its parts: ``except UnknownChannelError`` does
    not catch a broadcast in which one channel of many was unknown, nor one
    into a single channel - the broadcast as a whole is not unknown. Look at
    each channel's error in ``failed``.
    """

    failed: list[ChannelResult]
    total: int
    result: BroadcastResult

    def __init__(self, failed: list[ChannelResult], total: int, result: BroadcastResult) -> None:
        super().__init__(len(failed), total)
        # The channels which failed, with their errors, in the order of the
        # request.
        self.failed = failed
        # How many channels the broadcast had.
        self.total = total
        # Every channel's outcome.
        self.result = result

    def retryable_channels(self) -> list[str]:
        """The channels whose failure is retryable, in the order of the request:
        the channels a retry should go to, with the same idempotency_key.
        Channels which failed for good, such as an unknown channel, are left
        out."""
        return [f.channel for f in self.failed if f.error is not None and retryable(f.error)]

    def __str__(self) -> str:
        msg = _failures_message(
            "broadcast",
            "channels",
            "got the publication",
            total=self.total,
            items=((f.channel, f.error) for f in self.failed),
            failed=len(self.failed),
        )
        if self.retryable_channels():
            msg += " (retry only retryable_channels(), with the same idempotency_key)"
        return msg

    def __repr__(self) -> str:
        return f"{type(self).__name__}(failed={len(self.failed)}, total={self.total})"


class FailedCommand:
    """The failure of one command of a batch."""

    __slots__ = ("error", "index", "method")

    def __init__(self, index: int, method: str, error: Exception) -> None:
        # The command's position in the batch, from zero.
        self.index = index
        # Its API method, such as "publish".
        self.method = method
        # The error its pending returns: an ApiError, or a
        # BroadcastFailedChannelsError for a broadcast which failed in one or
        # more channels.
        self.error = error

    def __repr__(self) -> str:
        return f"FailedCommand(index={self.index}, method={self.method!r}, error={self.error!r})"


class BatchFailedCommandsError(CentError):
    """A batch in which one or more commands failed, up to all of them. Every
    command got its own reply: each pending holds its outcome. ``result`` is
    the batch's.

    It is not an ApiError of its parts: look at each command's error in
    ``failed``, or at its pending.
    """

    failed: list[FailedCommand]
    total: int
    result: BatchResult

    def __init__(self, failed: list[FailedCommand], total: int, result: BatchResult) -> None:
        super().__init__(len(failed), total)
        self.failed = failed
        self.total = total
        self.result = result

    def __str__(self) -> str:
        return _failures_message(
            "batch",
            "commands",
            "succeeded",
            total=self.total,
            items=((f"#{f.index} {f.method}", f.error) for f in self.failed),
            failed=len(self.failed),
        )

    def __repr__(self) -> str:
        return f"{type(self).__name__}(failed={len(self.failed)}, total={self.total})"


def _failures_message(
    op: str, parts: str, rest: str, *, total: int, items: Iterable[tuple[str, BaseException | None]], failed: int
) -> str:
    """ "broadcast: 2 of 4 channels failed, 2 got the publication: a: ...; b: ..." """
    s = f"{op}: {failed} of {total} {parts} failed"
    if failed < total:
        s += f", {total - failed} {rest}"
    named = []
    for i, (label, err) in enumerate(items):
        if i == _MAX_ERROR_ITEMS:
            named.append(f"and {failed - i} more")
            break
        named.append(f"{label}: {err}")
    if named:
        s += ": " + "; ".join(named)
    return s


def retryable(err: BaseException | None) -> bool:
    """Whether a new attempt, with time left, may succeed after err: the error
    came from a temporary condition, not from the request.

    Retryable are an ApiError Centrifugo marked temporary, and code 100 from
    Centrifugo versions which did not mark errors yet; a network failure; a
    timeout, also a caller's own; an HTTPError 429 or 5xx; a broadcast or batch
    partial error with at least one retryable part.

    Not retryable are the request's own errors - an unknown channel, a bad
    request, InvalidRequestError - and InvalidConfigError, ClosedError, a
    cancelled call, a DecodeError, rejected credentials and an invalid TLS
    certificate.

    A retryable error does not mean nothing was done: retry a publication
    only with the same idempotency_key. Retry a broadcast with
    broadcast_with_retry, or only its retryable_channels(): repeating the call
    resends to the channels which already got it.
    """
    if err is None:
        return False
    if isinstance(err, BroadcastFailedChannelsError):
        return any(f.error is not None and retryable(f.error) for f in err.failed)
    if isinstance(err, BatchFailedCommandsError):
        return any(retryable(f.error) for f in err.failed)
    if isinstance(err, ApiError):
        return err.temporary or err.code == InternalError.CODE
    if isinstance(err, HTTPError):
        return err.status_code == 429 or err.status_code >= 500
    if isinstance(err, TimeoutError):
        return True
    if isinstance(err, NetworkError):
        cause = err.__cause__
        while cause is not None:
            if isinstance(cause, ssl.SSLCertVerificationError):
                return False
            cause = cause.__cause__ or cause.__context__
        return True
    return False
