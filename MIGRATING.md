# Migrating from cent 5 to cent 6

cent 6 is a rewrite to the [Centrifugo server SDK
specification](https://github.com/centrifugal/gocent/blob/master/spec.md). Four
complete programs below, as written with cent 5 and with cent 6: publishing,
broadcasting, a batch, and the same from asyncio code. Each pair does the same
thing. The sections after them map every client option, call and error.

What changes most:

1. **A broadcast or batch in which some parts failed now raises.** cent 5
   returned normally and left the failed channels and commands in the result,
   for you to find. cent 6 raises `BroadcastFailedChannelsError` or
   `BatchFailedCommandsError`, whose `result` holds every part's outcome. See
   [Failed channels are errors now](#failed-channels-are-errors-now).
2. **Requests and results are dataclasses**, generated from Centrifugo's
   protos - no pydantic.
3. **Exceptions have new names and more kinds**: [Errors](#errors).
4. **Python 3.11 or newer**, and **httpx2** - the maintained fork of httpx -
   instead of requests and aiohttp.
5. **A request the client can tell is wrong fails before sending**, with
   `InvalidRequestError`: a required field given empty, which cent 5 sent
   and Centrifugo refused with code 107. See [What is sent](#what-is-sent).

```
pip install --upgrade "cent>=6"
```

## Publish

cent 5:

```python
import os

from cent import CentApiResponseError, Client, PublishRequest

client = Client("http://localhost:8000/api", os.environ["CENTRIFUGO_API_KEY"], timeout=5.0)

request = PublishRequest(
    channel="news",
    data={"text": "hello"},
    tags={"kind": "greeting"},
    idempotency_key="event-1",
)
try:
    result = client.publish(request)
except CentApiResponseError as e:
    if e.code == 102:
        raise SystemExit("no such namespace") from e
    raise
print(f"published at offset {result.offset}")
```

cent 6:

```python
import os

import cent

client = cent.Client("http://localhost:8000/api", api_key=os.environ["CENTRIFUGO_API_KEY"], request_timeout=5.0)

try:
    result = client.publish(
        channel="news",
        data={"text": "hello"},
        tags={"kind": "greeting"},
        idempotency_key="event-1",
    )
except cent.UnknownChannelError as e:
    raise SystemExit("no such namespace") from e
print(f"published at offset {result.offset}")
client.close()
```

- `api_key` is a keyword argument, and `timeout` became `request_timeout`; a
  call still takes its own: `client.publish(channel=..., data=..., timeout=1.0)`.
- A known error code is raised as its own class - `UnknownChannelError` for
  102 - so there is no need to compare `code` by hand. Any Centrifugo error is
  still an `ApiError` with `code` and `message`.
- `close()`, or `with cent.Client(...) as client:`, waits for calls in progress
  and closes the connections.

## Broadcast

cent 5:

```python
import os

from cent import BroadcastRequest, Client

client = Client("http://localhost:8000/api", os.environ["CENTRIFUGO_API_KEY"], timeout=5.0)

channels = ["user:1", "user:2", "user:3"]
result = client.broadcast(BroadcastRequest(channels=channels, data={"text": "hello"}, idempotency_key="notice-1"))
# A channel which failed shows only here: broadcast returned normally.
for channel, response in zip(channels, result.responses):
    if response.error:
        print(f"not published into {channel}: {response.error.message} ({response.error.code})")
        continue
    print(f"{channel}: offset {response.result.offset}")
```

cent 6:

```python
import os

import cent

client = cent.Client("http://localhost:8000/api", api_key=os.environ["CENTRIFUGO_API_KEY"], request_timeout=5.0)

try:
    result = client.broadcast(
        channels=["user:1", "user:2", "user:3"], data={"text": "hello"}, idempotency_key="notice-1"
    )
except cent.BroadcastFailedChannelsError as e:
    # Centrifugo replied, and some channels failed: e.result has every channel.
    # This program reports each failed channel, as the cent 5 one did.
    result = e.result
for ch in result.channels:
    if ch.error is not None:
        print(f"not published into {ch.channel}: {ch.error}")
        continue
    print(f"{ch.channel}: offset {ch.result.offset}")
client.close()
```

- In cent 5 a broadcast which failed in some channels returned normally. In
  cent 6 it raises `BroadcastFailedChannelsError` then - see below.
- Each entry of `result.channels` names its channel: no more zipping the
  request's channels with the responses.
- Retried with the same `idempotency_key`, the broadcast is not published
  again into channels which already have it.

### Failed channels are errors now

**The mistake cent 5 made easy.** `broadcast` returned normally as long as the
request reached Centrifugo, even when some channels failed: their errors were
only in `result.responses`. So the usual Python code

```python
client.broadcast(cent.BroadcastRequest(channels=channels, data=data))
```

treated a broadcast with failed channels as a success. Those channels did not
get the publication - a channel in a namespace removed from the configuration,
say, or channels on a Redis shard which was briefly down - and nothing logged
or retried it. Code which checked every response was right; the trap was that
leaving the check out was the natural way to write the call.

**What cent 6 does.** The call returns only when every channel got the
publication. When Centrifugo ran the broadcast and some channels failed, it
raises `BroadcastFailedChannelsError` listing them in `failed`, with every
channel's outcome in `result` - so an unhandled failure is seen, and a
temporary one can be retried. Check code which only called `broadcast`: it now
reports failures it used to miss, which is the point.

**When to keep cent 5's behaviour.** Code which already handled every channel
on its own may want a broadcast with some failed channels to go on, as in cent
5 - catch `BroadcastFailedChannelsError` and read `e.result`, as the program
above does. Do this only where failed channels are expected and handled.
Elsewhere, let the exception through.

**Retries are built for broadcast.** `client.broadcast_with_retry(channels=..., data=...)`
retries only the channels which may still succeed, with one `idempotency_key`
for all attempts - made for the call when the request has none - and returns
every channel's last outcome. A retry of the whole broadcast would publish
again into the channels which already got it.

## Batch

cent 5:

```python
import os

from cent import BatchRequest, Client, PresenceStatsRequest, PublishRequest

client = Client("http://localhost:8000/api", os.environ["CENTRIFUGO_API_KEY"], timeout=5.0)

result = client.batch(
    BatchRequest(
        requests=[
            PublishRequest(channel="news", data={"text": "hello"}),
            PresenceStatsRequest(channel="news"),
        ]
    )
)
published, stats = result.replies
print(f"published at offset {published.offset}; {stats.num_clients} clients in news")
```

cent 6:

```python
import os

import cent

client = cent.Client("http://localhost:8000/api", api_key=os.environ["CENTRIFUGO_API_KEY"], request_timeout=5.0)

batch = client.new_batch()
published = batch.publish(channel="news", data={"text": "hello"})
stats = batch.presence_stats(channel="news")
batch.send()  # raises unless every command succeeded
print(f"published at offset {published.result().offset}; {stats.result().num_clients} clients in news")
client.close()
```

- `client.new_batch()` replaces `BatchRequest`: each command returns a
  pending, whose `result()` is that command's result - or raises its error.
- `send()` raises `BatchFailedCommandsError` when any command failed, every
  command's outcome in its pending; cent 5 returned normally.
- `parallel=True` goes to `new_batch`: `client.new_batch(parallel=True)`.

## Async

cent 5:

```python
import asyncio
import os

from cent import AsyncClient, BroadcastRequest, PublishRequest


async def main() -> None:
    client = AsyncClient("http://localhost:8000/api", os.environ["CENTRIFUGO_API_KEY"], timeout=5.0)
    result = await client.publish(PublishRequest(channel="news", data={"text": "hello"}))
    print(f"published at offset {result.offset}")
    result = await client.broadcast(BroadcastRequest(channels=["user:1", "user:2"], data={"text": "hello"}))
    failed = [r for r in result.responses if r.error]
    print(f"broadcast: {len(failed)} channels failed")
    await client._session.close()


asyncio.run(main())
```

cent 6:

```python
import asyncio
import os

import cent


async def main() -> None:
    async with cent.AsyncClient(
        "http://localhost:8000/api", api_key=os.environ["CENTRIFUGO_API_KEY"], request_timeout=5.0
    ) as client:
        result = await client.publish(channel="news", data={"text": "hello"})
        print(f"published at offset {result.offset}")
        try:
            await client.broadcast(channels=["user:1", "user:2"], data={"text": "hello"})
            print("broadcast: 0 channels failed")
        except cent.BroadcastFailedChannelsError as e:
            print(f"broadcast: {len(e.failed)} channels failed")


asyncio.run(main())
```

- `AsyncClient` has the same methods as `Client`, awaited, with the same
  errors. `async with` closes it; so does `await client.aclose()`.
- An `asyncio.timeout()` around a call, or cancelling its task, ends it
  sooner than its timeout.

## Clients

```python
# cent 5
client = cent.Client(api_url, api_key, timeout=5.0, session=requests_session)
client = cent.AsyncClient(api_url, api_key, timeout=5.0, session=aiohttp_session)

# cent 6
client = cent.Client(api_url, api_key=api_key, request_timeout=5.0, http_client=httpx2.Client(...))
client = cent.AsyncClient(api_url, api_key=api_key, request_timeout=5.0, http_client=httpx2.AsyncClient(...))
```

- `api_key` is a keyword argument. `bearer_token_func` authenticates with
  Centrifugo PRO's API tokens instead - see `cent.token.APITokenSource`.
- `timeout` per call stays: `client.publish(channel=..., data=..., timeout=1.0)`.
  It replaces `request_timeout` for that call, longer or shorter. It must be
  positive: `timeout=0` raises `InvalidRequestError`; leave it `None` for
  `request_timeout`.
- An `http_client` you pass is never changed - cent 5 set the API key in the
  headers of the session you gave it.
- Redirects are not followed, so a misconfigured `http://` endpoint fails with
  a hint instead of turning a publication into a GET.
- Close a client when the application stops: `client.close()`,
  `await client.aclose()`, or `with` / `async with`.

## Calls

Methods take the request's fields as keyword arguments, instead of a request
object:

```python
client.publish(channel="news", data={"text": "hello"})
```

A batch has the same methods, and so do commands for async consumers:
`batch.publish(...)`, `cent.command.publish(...)`. A misspelled field raises
`TypeError` naming it.

- `info()`, and the other methods whose request has no fields, take no
  argument.
- `BoolValue(value=True)` fields are plain `bool | None` now:
  `cent.SubscribeOptionOverride(presence=True)`. `None` leaves the option as
  configured.
- A payload which is not JSON - NaN, bytes - raises `InvalidRequestError`
  before sending. JSON text you already have goes in `cent.RawJSON(text)`.
- `request.api_payload`, for async consumers, is now
  `cent.command.publish(...)` and the like: its `method` and `payload`, or
  `to_json()`. It validates the request first.

## Types

The request classes - `PublishRequest`, `BroadcastRequest`, `BatchRequest`
and the rest - are gone from the public API: the methods take their fields
as keyword arguments. So are `CentRequest`, `CentResult` and `Response`. The
nested and result types keep their names and fields, as the protos name
them, but for these:

| cent 5 | cent 6 |
|---|---|
| `ChannelOptionsOverride` | `SubscribeOptionOverride` |
| `BoolValue(value=True)` | `True`: the fields are `bool \| None` |
| `Node` | `NodeResult` |
| `ProcessStats` | `Process` |
| `ChannelInfoResult` | `ChannelInfo` |

They are dataclasses, not pydantic models: build them with keyword arguments,
read their attributes, and render them with `cent.to_dict(result)` rather
than `model_dump()`.

A nested type's required fields are required keyword arguments, as they were
mostly in cent 5's models: `cent.DeviceTopicsUpdate(op="add", topics=[...])`,
`cent.RateLimitPolicy(rate=..., interval_ms=...)`. `DeviceTopicsUpdate.topics`
and `PushRateLimitStrategy.policies`, required in cent 5, are optional now. Fixed sets of values have constants: `op=cent.OP_ADD`,
`provider=cent.PROVIDER_FCM`, `status=cent.STATUS_DELIVERED`; the fields stay
strings.

## What is sent

cent 5 sent every field which was not `None`. cent 6 sends what has a value:

- **A required field given empty fails before sending.** `channel=""`,
  `users=[]`, or a required nested message with nothing set raise
  `InvalidRequestError` naming the field's path -
  `invalid send_push_notification request: limit_strategy.rate_limit.policies[0].rate is required`.
  cent 5 sent them, and Centrifugo answered with code 107,
  `CentApiResponseError`. A required field whose empty value means something
  is still sent empty: `invalidate_user_tokens(user="")` is anonymous users,
  `user_topic_update(user="", ...)` the global binding.
- **Zero values are not sent**: an empty string, 0, `False`, an empty list -
  Centrifugo reads them as unset anyway.
- **A nested message with nothing set is not sent.** cent 5 sent
  `"limit_strategy": {}` for `PushLimitStrategy()`, which Centrifugo PRO
  refuses with code 107. The exception is `device_update`'s updates: an
  empty `cent.DeviceUserUpdate(user="")` is sent, and detaches the devices
  from their user, as an empty timezone, locale or meta update clears it;
  leave an update `None` to change nothing.

## Errors

| cent 5 | cent 6 |
|---|---|
| `CentError` | `CentError` |
| `CentApiResponseError` (`code`, `message`) | `ApiError` (`code`, `message`, `temporary`), raised as the subclass of its code: `UnknownChannelError`, `NotFoundError`, `BadRequestError`, `NotAvailableError`, `TooManyRequestsError`, `InternalError`... |
| `CentTransportError` (`status_code`) | `HTTPError` (`status_code`, `body`, `headers`) |
| `CentUnauthorizedError` | `UnauthorizedError`, a kind of `HTTPError` |
| `CentNetworkError` | `NetworkError` |
| `CentTimeoutError` | `CentTimeoutError`, now also a builtin `TimeoutError` |
| `CentDecodeError` | `DecodeError` |
| - | `InvalidRequestError`, `InvalidConfigError`, `FunctionError`, `ClosedError`, `BroadcastFailedChannelsError`, `BatchFailedCommandsError` |

`cent.retryable(err)` says whether retrying may succeed. Retry a publication
only with an `idempotency_key`.

Two error paths are new: `api_endpoint_func` and `bearer_token_func`, which
cent 5 did not have, fail a call with `InvalidConfigError` for an endpoint or
token they return which cannot be sent, and with `FunctionError` - the
function's exception as its `__cause__` - when they raise.

## New in cent 6

Tokens (`cent.token`, with `token.APITokenSource` for Centrifugo PRO's API
tokens), the endpoints client SDKs call (`cent.endpoints`), the proxy
handlers (`cent.proxy`), shared poll signatures (`cent.sharedpoll`),
automatic batching, the map and shared poll API methods, `<method>_all`
iterators over paged methods, `position()` on results holding a stream
position, constants for fields with a fixed set of values, `on_request` for
metrics. See the [README](README.md) and the
[changelog](CHANGELOG.md).
