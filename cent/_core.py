"""What Client and AsyncClient share: configuration, headers, and reading
replies. No I/O happens here."""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx2

from cent._api import METHODS
from cent._broadcast import api_error
from cent._errors import (
    ApiError,
    CentTimeoutError,
    DecodeError,
    HTTPError,
    InvalidConfigError,
    InvalidRequestError,
    NetworkError,
    UnauthorizedError,
)

USER_AGENT = "pycent/6"

DEFAULT_REQUEST_TIMEOUT = 10.0
DEFAULT_MAX_BATCH_SIZE = 1000

# The body of an unexpected status is read up to MAX_API_ERROR_BYTES for a
# Centrifugo error in it, MAX_ERROR_BODY_BYTES of it kept for the HTTPError,
# and the rest drained up to MAX_DRAIN_BYTES, so that the connection is reused.
MAX_ERROR_BODY_BYTES = 512
MAX_API_ERROR_BYTES = 4 << 10
MAX_DRAIN_BYTES = 64 << 10

# The connection pool of the default HTTP clients: up to 256 connections to a
# host, all kept while idle, so that a burst does not open connections only to
# close them; idle ones closed after 50 seconds, before load balancers commonly
# close theirs.
POOL_LIMITS = httpx2.Limits(max_connections=256, max_keepalive_connections=256, keepalive_expiry=50)

# Statuses Centrifugo's transport error mode maps errors to.
_TRANSPORT_MODE_STATUSES = {400, 404, 409, 416, 429, 500}
_MIN_ERROR_CODE = 100


@dataclass(slots=True, kw_only=True)
class RequestInfo:
    """One HTTP request to Centrifugo's API, for on_request."""

    method: str
    """The API method: "publish", say, or "batch" for a batch."""

    commands: int
    """How many commands the request carried: 1, or a batch's size."""

    failed: int = 0
    """How many of them Centrifugo answered with an error. A broadcast which
    failed in some channels is not counted: its command was answered."""

    auto_batch: bool = False
    """True for a batch made of concurrent calls by automatic batching."""

    duration: float = 0.0
    """Seconds from before getting the endpoint and credentials to the reply read."""

    status_code: int = 0
    """The HTTP status of the reply, 0 without one."""

    error: Exception | None = None
    """The request's own error: the network, a timeout, an HTTP status, a reply
    which is not Centrifugo's, a request refused before sending - or, in the
    transport error mode, the error of its one command. None when Centrifugo's
    reply was read."""


def check_endpoint(addr: str, option: str = "api_endpoint") -> str:
    """addr without a trailing slash, or InvalidConfigError naming what is wrong."""
    if not isinstance(addr, str):
        raise InvalidConfigError(f"{option} must be a str, not {type(addr).__name__}")
    try:
        u = urlsplit(addr)
        _ = u.port  # raises for a port which is not a number
    except ValueError as e:
        raise InvalidConfigError(f"{option}: {addr!r} is not a valid URL: {e}") from None
    if u.scheme not in ("http", "https"):
        raise InvalidConfigError(f"{option}: {addr!r} must be an absolute http:// or https:// URL")
    if not u.hostname:
        raise InvalidConfigError(f"{option}: {addr!r} has no host")
    if u.query or u.fragment or u.username is not None or u.password is not None:
        raise InvalidConfigError(f"{option}: {addr!r} must not have a query, fragment or credentials; use api_key")
    path = u.path.rstrip("/")
    last = path.rsplit("/", 1)[-1]
    if last in METHODS:
        raise InvalidConfigError(
            f"{option}: {addr!r} ends with the method {last!r}; it is the API base URL, "
            "such as http://localhost:8000/api"
        )
    return urlunsplit((u.scheme, u.netloc, path, "", ""))


def valid_header_name(name: str) -> bool:
    return bool(name) and all(0x20 < ord(c) < 0x7F and c not in '"(),/:;<=>?@[\\]{}' for c in name)


def valid_header_value(value: str) -> bool:
    """Printable ASCII and tab: what HTTP header values carry without an encoding."""
    return all((0x20 <= ord(c) < 0x7F) or c == "\t" for c in value)


class Config:
    """A client's checked configuration."""

    def __init__(
        self,
        *,
        api_endpoint: str | None,
        api_endpoint_func: Callable[[], Any] | None,
        api_key: str,
        bearer_token_func: Callable[[], Any] | None,
        request_timeout: float | None,
        headers: Mapping[str, str] | None,
        on_request: Callable[[RequestInfo], None] | None,
    ) -> None:
        if api_endpoint is None and api_endpoint_func is None:
            raise InvalidConfigError("api_endpoint is required, for example http://localhost:8000/api")
        if api_endpoint is not None and api_endpoint_func is not None:
            raise InvalidConfigError("set api_endpoint or api_endpoint_func, not both")
        self.endpoint = check_endpoint(api_endpoint) if api_endpoint is not None else ""
        if api_endpoint_func is not None and not callable(api_endpoint_func):
            raise InvalidConfigError("api_endpoint_func must be callable")
        self.endpoint_func = api_endpoint_func

        if not isinstance(api_key, str):
            raise InvalidConfigError(f"api_key must be a str, not {type(api_key).__name__}")
        if api_key and bearer_token_func is not None:
            raise InvalidConfigError(
                "set api_key or bearer_token_func, not both: a request with a bearer token is judged by the token alone"
            )
        if not valid_header_value(api_key):
            raise InvalidConfigError("api_key must be printable ASCII: no line breaks, control or non-ASCII characters")
        if bearer_token_func is not None and not callable(bearer_token_func):
            raise InvalidConfigError("bearer_token_func must be callable")
        self.token_func = bearer_token_func

        hdrs: dict[str, str] = {}
        for k, v in (headers or {}).items():
            lk = k.lower()
            if lk == "x-api-key":
                raise InvalidConfigError("headers may not set X-API-Key; use api_key")
            if lk == "authorization":
                raise InvalidConfigError("headers may not set Authorization; use bearer_token_func")
            if lk == "content-type":
                raise InvalidConfigError("headers may not set Content-Type")
            if not valid_header_name(k):
                raise InvalidConfigError(f"headers: {k!r} is not a valid HTTP header name")
            if not isinstance(v, str) or not valid_header_value(v):
                raise InvalidConfigError(
                    f"headers: {k} must be printable ASCII: no line breaks, control or non-ASCII characters"
                )
            if lk == "host" and not v:
                raise InvalidConfigError("headers: Host must not be empty")
            hdrs[k] = v
        hdrs["Content-Type"] = "application/json"
        if not any(k.lower() == "user-agent" for k in hdrs):
            hdrs["User-Agent"] = USER_AGENT
        if api_key:
            hdrs["X-API-Key"] = api_key
        self.headers = hdrs

        if request_timeout is None:
            request_timeout = DEFAULT_REQUEST_TIMEOUT
        if isinstance(request_timeout, bool) or not isinstance(request_timeout, (int, float)):
            raise InvalidConfigError("request_timeout must be a number of seconds")
        if request_timeout <= 0:
            raise InvalidConfigError("request_timeout must be positive")
        self.request_timeout = float(request_timeout)
        if on_request is not None and not callable(on_request):
            raise InvalidConfigError("on_request must be callable")
        self.on_request = on_request

    def deadline(self, timeout: float | None) -> float:
        """The monotonic deadline of a call with timeout, or request_timeout."""
        if timeout is None:
            timeout = self.request_timeout
        elif isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout < 0:
            raise InvalidRequestError("timeout must be a non-negative number of seconds")
        return time.monotonic() + timeout

    def request_headers(self, token: str | None) -> dict[str, str]:
        h = dict(self.headers)
        if token is not None:
            h["Authorization"] = "Bearer " + token
        return h

    def report(self, info: RequestInfo, start: float, error: Exception | None) -> None:
        if self.on_request is None:
            return
        info.duration = time.monotonic() - start
        info.error = error
        self.on_request(info)


def checked_endpoint(addr: Any) -> str:
    """The endpoint an api_endpoint_func returned, checked."""
    try:
        return check_endpoint(addr, "api_endpoint_func")
    except InvalidConfigError as e:
        raise InvalidConfigError(str(e)) from None


def checked_token(token: Any) -> str:
    if not isinstance(token, str) or not token or not valid_header_value(token):
        raise InvalidConfigError(
            "bearer_token_func returned an empty token, not a str, or one which is not printable ASCII"
        )
    return token


def remaining(deadline: float, method: str) -> float:
    """Seconds left until deadline, or CentTimeoutError when none are."""
    left = deadline - time.monotonic()
    if left <= 0:
        raise CentTimeoutError(f"{method}: timed out")
    return left


def http_error(method: str, status: int, body: bytes, headers: Mapping[str, str]) -> Exception:
    """The error of a reply with status other than 200: a Centrifugo error in
    the transport error mode, an HTTPError otherwise."""
    if status in _TRANSPORT_MODE_STATUSES:
        try:
            d = json.loads(body)
        except (ValueError, RecursionError):
            d = None
        # A body whose code is an HTTP error status - {"code": 429} from a rate
        # limiting gateway - is a gateway's, not Centrifugo's.
        if isinstance(d, dict) and isinstance(d.get("code"), int) and not isinstance(d.get("code"), bool):
            code = d["code"]
            if code >= _MIN_ERROR_CODE and not 400 <= code < 600:
                try:
                    return api_error(d, "error")
                except DecodeError:
                    pass
    cls = UnauthorizedError if status == 401 else HTTPError
    err = cls(status, body[:MAX_ERROR_BODY_BYTES].strip(), headers)
    if METHODS.get(method):
        err._pro_method = method
    return err


def envelope(body: bytes, method: str) -> tuple[dict[str, Any], ApiError | None]:
    """The decoded reply of a method: its result, or its error."""
    try:
        d = json.loads(body)
    except (ValueError, RecursionError) as e:
        raise DecodeError(f"{method}: the reply is not JSON: {e}") from e
    if not isinstance(d, dict):
        raise DecodeError(f"{method}: the reply is not a JSON object")
    if (error := d.get("error")) is not None:
        return {}, api_error(error, "error")
    result = d.get("result")
    if result is None:
        return {}, None
    if not isinstance(result, dict):
        raise DecodeError(f"{method}: result: expected an object")
    return result, None


def batch_replies(body: bytes, n: int) -> list[dict[str, Any]]:
    """The replies of a batch of n commands."""
    try:
        d = json.loads(body)
    except (ValueError, RecursionError) as e:
        raise DecodeError(f"batch: the reply is not JSON: {e}") from e
    if not isinstance(d, dict):
        raise DecodeError("batch: the reply is not a JSON object")
    if (error := d.get("error")) is not None:
        raise api_error(error, "error")
    replies = d.get("replies")
    if replies is None:
        replies = []
    if not isinstance(replies, list) or not all(isinstance(r, dict) for r in replies):
        raise DecodeError("batch: replies: expected an array of objects")
    if len(replies) != n:
        raise DecodeError(f"batch: got {len(replies)} replies for {n} commands")
    return replies


def transport_error(method: str, err: Exception) -> Exception:
    """The error of a request which failed on its way."""
    if isinstance(err, httpx2.TimeoutException):
        return CentTimeoutError(f"{method}: timed out: {err}")
    return NetworkError(f"{method}: {type(err).__name__}: {err}")


def command_error(reply: dict[str, Any], i: int, method: str) -> ApiError | None:
    """The error of a batch command's reply, if it has one. A PRO method's code
    104 hints that the server may be Centrifugo OSS."""
    e = reply.get("error")
    if e is None:
        return None
    err = api_error(e, f"replies[{i}].error")
    if err.code == 104 and METHODS.get(method):
        err._pro_method = method
    return err


def default_http_client() -> httpx2.Client:
    """The HTTP client of a Client created without one: no timeouts of its own,
    each request given the time left until its deadline."""
    return httpx2.Client(limits=POOL_LIMITS, follow_redirects=False, timeout=None)


def default_async_http_client() -> httpx2.AsyncClient:
    """The HTTP client of an AsyncClient created without one."""
    return httpx2.AsyncClient(limits=POOL_LIMITS, follow_redirects=False, timeout=None)
