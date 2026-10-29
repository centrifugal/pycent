"""Signatures for shared poll subscriptions.

See https://centrifugal.dev/docs/server/shared_poll. Shared poll
subscriptions are experimental in Centrifugo, and this module follows their
changes.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from collections.abc import Sequence
from datetime import datetime

from cent._errors import InvalidRequestError
from cent.token import NEVER, Never

__all__ = ["sign"]


def sign(secret: bytes | str, *, user: str, channel: str, keys: Sequence[str], expires_at: datetime | Never) -> str:
    """The signature authorizing user to track keys in channel until expires_at,
    as Centrifugo verifies it: "iat:exp:hmac", iat now and exp expires_at in
    Unix seconds. expires_at is required, as a token's expiry is: an aware
    datetime, or token.NEVER for a signature which never expires. secret is
    Centrifugo's shared_poll.hmac_secret_key; user is the ID of the
    connection's user, empty for an anonymous one.

    The signature covers exactly keys, in their order: a client tracking other
    keys, or the same in another order, is refused. The arguments but secret
    are keyword-only, so that a user and a channel cannot be swapped:

    >>> sharedpoll.sign(secret, user="42", channel="poll:prices", keys=["AAPL"], expires_at=exp)
    """
    return _sign_at(secret, user, channel, keys, expires_at, now=int(time.time()))


def _sign_at(
    secret: bytes | str, user: str, channel: str, keys: Sequence[str], expires_at: datetime | Never, *, now: int
) -> str:
    """sign, at the Unix time now: for the spec's test vectors."""
    s = secret.encode() if isinstance(secret, str) else bytes(secret)
    if not s:
        raise InvalidRequestError("sharedpoll: empty secret")
    exp = "0"
    if expires_at is not NEVER:
        if not isinstance(expires_at, datetime):
            raise TypeError(
                f"sharedpoll: expires_at must be a datetime, or token.NEVER for a signature which never "
                f"expires - not {type(expires_at).__name__}"
            )
        if expires_at.tzinfo is None or expires_at.utcoffset() is None:
            raise InvalidRequestError("sharedpoll: expires_at is a naive datetime: give it a time zone")
        exp = str(int(expires_at.timestamp()))
    iat = str(now)
    keys_hash = hashlib.sha256("\x00".join(keys).encode()).hexdigest()
    # NUL-separated, so that a colon in a user or channel cannot move between
    # fields: ("alice", "news:tech") and ("alice:news", "tech") sign
    # differently.
    msg = "\x00".join((iat, exp, user, channel, keys_hash)).encode()
    return f"{iat}:{exp}:{hmac.new(s, msg, hashlib.sha256).hexdigest()}"
