# Migrating from cent 5 to cent 6

cent 6 is a rewrite to the [Centrifugo server SDK
specification](https://github.com/centrifugal/gocent/blob/v4_dev/spec.md). Most
code changes little - requests keep their names and fields - but four things
need care:

1. **A broadcast or batch in which some parts failed now raises.** cent 5
   returned normally and left the failed channels and commands in the result,
   for you to find. cent 6 raises `BroadcastFailedChannelsError` or
   `BatchFailedCommandsError`, whose `result` holds every part's outcome.
2. **Requests and results are dataclasses**, generated from Centrifugo's
   protos - no pydantic. Results are no longer pydantic models.
3. **Exceptions have new names and more kinds** - see the table below.
4. **Python 3.11 or newer**, and **httpx2** instead of requests and aiohttp.

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
  Centrifugo PRO's API tokens instead - see `cent.token.APITokens`.
- `timeout` per call stays: `client.publish(request, timeout=1.0)`.
- An `http_client` you pass is never changed - cent 5 set the API key in the
  headers of the session you gave it.
- Redirects are not followed, so a misconfigured `http://` endpoint fails with
  a hint instead of turning a publication into a GET.
- Close a client when the application stops: `client.close()`,
  `await client.aclose()`, or `with` / `async with`.

## Calls

Methods take the same request objects:

```python
client.publish(cent.PublishRequest(channel="news", data={"text": "hello"}))
```

- `info()`, and the other methods whose request has no fields, take no
  argument.
- `BoolValue(value=True)` fields are plain `bool | None` now:
  `cent.SubscribeOptionOverride(presence=True)`. `None` leaves the option as
  configured.
- A payload which is not JSON - NaN, bytes - raises `InvalidRequestError`
  before sending. JSON text you already have goes in `cent.RawJSON(text)`.
- `request.api_method` stays. `request.api_payload`, for async consumers, is
  now `cent.new_command(request)`: its `method` and `payload`, or `to_json()`.
  It validates the request first.

## Broadcast and batch

```python
# cent 5: broadcast returned; failed channels hid in the responses
result = client.broadcast(cent.BroadcastRequest(channels=channels, data=data))
for response in result.responses:
    if response.error:
        ...

# cent 6: it raises when any channel failed
try:
    client.broadcast(cent.BroadcastRequest(channels=channels, data=data))
except cent.BroadcastFailedChannelsError as e:
    for ch in e.failed:  # ChannelResult: channel, error, result
        ...
```

Batches are built with `client.new_batch()`, each command returning a pending
result:

```python
# cent 5
result = client.batch(cent.BatchRequest(requests=[req1, req2], parallel=True))
result.replies[0]

# cent 6
batch = client.new_batch(parallel=True)
p1 = batch.publish(req1)
p2 = batch.presence(req2)
batch.send()  # raises BatchFailedCommandsError when any command failed
p1.result()
```

To retry a broadcast, use `client.broadcast_with_retry(request)`: it retries
only the channels which may still succeed, with one idempotency key.

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
| - | `InvalidRequestError`, `InvalidConfigError`, `ClosedError`, `BroadcastFailedChannelsError`, `BatchFailedCommandsError` |

`cent.retryable(err)` says whether retrying may succeed. Retry a publication
only with an `idempotency_key`.

## New in cent 6

Tokens (`cent.token`), the endpoints client SDKs call (`cent.endpoints`), the
proxy handlers (`cent.proxy`), shared poll signatures (`cent.sharedpoll`),
automatic batching, the map and shared poll API methods, `on_request` for
metrics. See the [README](README.md).
