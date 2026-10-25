"""Retry helpers: backoff, and what broadcast_with_retry tells its callback."""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass

from cent._broadcast import BroadcastResult, ChannelResult


def exponential_backoff(base: float, limit: float) -> Callable[[int], float]:
    """The wait, in seconds, before retrying after a failed attempt, attempt 1
    being the first failure: base after it, twice as long after each next one,
    up to limit. Each wait is a random time between half of it and all of it,
    so that clients which failed together do not all retry at the same moment.
    A negative base counts as zero, a limit below base as base, and an attempt
    below 1 as 1.

    In a retry loop of your own - a publication retried with the same
    idempotency_key::

        backoff = cent.exponential_backoff(0.1, 2.0)
        for attempt in itertools.count(1):
            try:
                return client.publish(request)
            except cent.CentError as e:
                if not cent.retryable(e) or attempt == 3:
                    raise
            time.sleep(backoff(attempt))   # await asyncio.sleep(...) in async code

    Retry a broadcast with broadcast_with_retry instead: repeating it resends
    to the channels which already got it.
    """
    base = max(float(base), 0.0)
    limit = max(float(limit), base)

    def delay(attempt: int) -> float:
        d = base
        for _ in range(1, max(attempt, 1)):
            if d >= limit:
                break
            d *= 2
        d = min(d, limit)
        return random.uniform(d / 2, d)  # noqa: S311 - spreads retries out; nothing depends on it being unpredictable

    return delay


_default_backoff = exponential_backoff(0.1, 5.0)


def default_delay(attempt: int) -> float:
    return _default_backoff(attempt)


@dataclass(slots=True, kw_only=True)
class BroadcastAttempt:
    """A failed attempt of broadcast_with_retry, given to its on_attempt_error."""

    attempt: int
    """The attempt which failed, from 1."""

    error: Exception
    """Its error: BroadcastFailedChannelsError when Centrifugo replied and some
    channels failed, otherwise the error of the request as a whole."""

    retry: list[ChannelResult]
    """The channels the next attempt sends, with the errors this attempt failed
    them with. A broadcast to many channels which all failed lists every one:
    log a count or a few."""

    result: BroadcastResult
    """Every channel's outcome so far, as the call would return it if it
    stopped now. It is the call's own, updated by later attempts: copy what you
    keep."""

    idempotency_key: str
    """The key every attempt is sent with."""
