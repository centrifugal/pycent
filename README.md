# cent

Python SDK for the [HTTP server API](https://centrifugal.dev/docs/server/server_api)
of [Centrifugo](https://github.com/centrifugal/centrifugo): every API method,
including those of Centrifugo PRO, in a blocking `Client` and an async
`AsyncClient`; connection, subscription and server API tokens; the proxy
handlers and the endpoints client SDKs call. For a real-time client over
WebSocket, see [centrifuge-python](https://github.com/centrifugal/centrifuge-python).

```
pip install cent            # httpx2 is the only dependency
pip install cent[crypto]    # RSA, ECDSA and Ed25519 tokens, with cryptography
```

| | Version |
|---|---|
| Python | 3.11 or newer |
| Centrifugo | v6, any release |
| Map and shared poll methods | Centrifugo v6.8.0 or newer |
| `ApiError.temporary`, `TooManyRequestsError`, refused requests reported as such rather than as internal errors | Centrifugo v6.10.0 or newer |
| Ed25519 tokens verified without JWKS, by `client.token.ed25519_public_key` | Centrifugo v6.10.2 or newer |
| Methods marked "Centrifugo PRO only" | Centrifugo PRO v6 |

cent 6 replaces cent 5: see [MIGRATING.md](MIGRATING.md). cent implements the
[Centrifugo server SDK specification](https://github.com/centrifugal/gocent/blob/v4_dev/spec.md),
version 0.1.

## Example

```python
import os
import cent

client = cent.Client("http://localhost:8000/api", api_key=os.environ["CENTRIFUGO_API_KEY"])

res = client.publish(channel="news", data={"text": "hello"})
print(f"published at offset {res.offset}")
```

And from asyncio code, the same methods awaited:

```python
async with cent.AsyncClient("http://localhost:8000/api", api_key=key) as client:
    await client.publish(channel="news", data={"text": "hello"})
```

Every API method takes its request's fields as keyword arguments - generated
from Centrifugo's `api.proto`, each documented - and returns its result, a
dataclass, raising unless Centrifugo did everything asked. A batch and
commands have the same methods: `batch.publish(...)`, `cent.command.publish(...)`.
Create the client once and share it: it is safe for concurrent use.

## Payloads

`data`, `info`, `meta` and the other payloads are JSON values, given as the
Python values they decode to - `dict`, `list`, `str`, `int`, `float`, `bool`,
`None` - and returned the same way: a payload from a reply sent back unchanged
is the same JSON value. A `str` is a JSON string. JSON you already have, or
encode with rules of your own, goes in `cent.RawJSON`, sent as it is:

```python
client.publish(channel="news", data=cent.RawJSON(row.payload_json))
```

A payload which is not JSON - NaN, bytes, a set - raises `InvalidRequestError`
before anything is sent. Binary data goes base64-encoded in the `b64` fields,
such as `b64data`.

Write integers which may pass 2^53 - a 64-bit ID, say - as JSON strings:
browsers and JavaScript backends decode JSON numbers as doubles, and round
larger integers silently.

## Timeouts

Each call takes a `timeout`, in seconds; without one, `request_timeout` - ten
seconds by default - bounds it:

```python
client.info(timeout=0.5)
```

The timeout bounds the whole call, connecting and reading included - also a
reply trickling in, headers and all. However a call times out, it raises
`cent.CentTimeoutError`, which is also a builtin `TimeoutError`. In asyncio code an `asyncio.timeout()` around a call, or
cancelling its task, ends it sooner.

`broadcast_with_retry` makes several requests in one call: its `timeout`
bounds them all, waits between them included, and `attempt_timeout` each one.

## Errors

| Exception | Meaning |
|---|---|
| `cent.ApiError` | Centrifugo refused the request or failed to carry it out: `code`, `message`, `temporary`. Known codes are subclasses: `UnknownChannelError`, `NotFoundError`, `BadRequestError`, `NotAvailableError`, `TooManyRequestsError`, `InternalError`... |
| `cent.BroadcastFailedChannelsError`, `cent.BatchFailedCommandsError` | some parts of a broadcast or batch failed - see below |
| `cent.HTTPError` | the request did not reach the API method: `status_code`, `body`, `headers`; `UnauthorizedError` for rejected credentials |
| `cent.DecodeError` | the reply was not Centrifugo's - usually `api_endpoint` points elsewhere |
| `cent.InvalidRequestError` | the client could tell the request is wrong and did not send it |
| `cent.InvalidConfigError` | the client was not created: the message names the option and the fix |
| `cent.NetworkError`, `cent.CentTimeoutError`, `cent.ClosedError` | as their names say |

All are `cent.CentError`. Centrifugo adds error codes over time: an unknown code
is still an `ApiError`, so match the codes you handle and treat the rest by
class.

## Retries

`cent.retryable(err)` reports whether a new attempt, with time left, may
succeed: the error came from a temporary condition - a broker being
unavailable, a rate limit, the network - not from the request.

A temporary error does not mean nothing was done: after a timeout, or even an
internal error, the publication may have happened. So retry a publication only
with an `idempotency_key`, and back off between a bounded number of attempts:

```python
request = dict(
    channel="orders:42",
    data=data,
    # The same key on every attempt: a publication which happened in an
    # earlier attempt, even one reported as failed, is not published again.
    idempotency_key="order-42-paid",
)
backoff = cent.exponential_backoff(0.2, 5.0)
for attempt in itertools.count(1):
    try:
        client.publish(**request)
        break
    except cent.CentError as e:
        if not cent.retryable(e) or attempt == 3:
            raise
    time.sleep(backoff(attempt))  # await asyncio.sleep(...) in async code
```

Choosing keys:

- One key per publication or broadcast, reused only to retry that same one. A
  broadcast needs one key, not one per channel.
- Centrifugo remembers a key per channel, for five minutes by default. A retry
  within that time is answered with the first result and not published again -
  and so is a *different* publication into the same channel under the same
  key. A key built from an ID must name the event too: `order-42-paid`, not
  `order-42`.
- The memory, Redis and PostgreSQL brokers keep keys. The NATS broker ignores
  them, so with it a retry publishes again.

Retry a broadcast with `broadcast_with_retry` rather than a loop: see below.

## Broadcast and batch

`broadcast` publishes the same data into many channels in one request; a batch
sends many commands at once. Both raise unless every part succeeded:

```python
client.broadcast(channels=["user:1", "user:2"], data={"text": "hello"}, idempotency_key=message_id)

batch = client.new_batch()
pub = batch.publish(channel="news", data=data)
stats = batch.presence_stats(channel="news")
batch.send()
pub.result()  # each command has its own result, or raises its own error
stats.result()
```

Parts succeed or fail on their own. When Centrifugo carried the request out
and some parts failed, up to all, it raises `BroadcastFailedChannelsError` or
`BatchFailedCommandsError`: its `failed` lists them, and its `result` holds
every part's outcome. Any other exception means the request failed as a whole
- the network, the credentials, an invalid request - and no part got a reply;
after a timeout or a network error Centrifugo may still have carried it out.

A partial error is not an error of its parts: `except UnknownChannelError` does
not catch a broadcast in which a channel was unknown, nor one into a single
channel - use `publish` for one channel. To go on despite some failed parts:

```python
try:
    client.broadcast(request)
except cent.BroadcastFailedChannelsError as e:
    log.warning("broadcast failed in %s", e.result.failed())
```

Retrying:

- a **broadcast**: `broadcast_with_retry` does it. It sends again only the
  channels which may still succeed, all attempts with one `idempotency_key` -
  made for the call when the request has none - and returns every channel's
  last outcome, as `broadcast` does:

  ```python
  res = client.broadcast_with_retry(request, max_attempts=5, attempt_timeout=2, timeout=10)
  ```

  By default it retries once, after about 100 milliseconds. `on_attempt_error`
  is called after each failed attempt which will be retried, with the channels
  to retry and their errors: it returns the seconds to wait before the next
  attempt - or `None` for the default backoff - and may log or count
  meanwhile; it raises to stop. A `HTTPError` in `a.error` carries the
  response's `headers`: wait at least its `Retry-After` to honour one.

  ```python
  backoff = cent.exponential_backoff(0.2, 5.0)


  def on_attempt_error(a: cent.BroadcastAttempt) -> float:
      log.info("attempt %d: %d channels to retry", a.attempt, len(a.retry))
      return backoff(a.attempt)
  ```

  `res.idempotency_key` is the key the attempts used: to retry the broadcast
  later, after it gave up - from a job queue, say - send it with that key.
  Repeating `broadcast` on any error would instead send it to every channel
  again, those which already got it included.
- a **batch**: build a new one, with the same keys, from the commands
  `e.failed` lists with a retryable error. A batch is sent once.

`new_batch()` runs the commands one by one, in order; `parallel=True` runs them
concurrently. Centrifugo PRO sends a batch's publications to its broker
together: each channel's publications still take effect in order, but
publications into different channels may not, unless the namespace sets
`publication_grouping_disabled`.

## Automatic batching

With `auto_batch`, calls made concurrently - from threads, or asyncio tasks -
go out together once enough requests are in flight, with no delay otherwise,
since nothing waits for a timer:

```python
client = cent.Client(endpoint, api_key=key, auto_batch=cent.AutoBatch(max_in_flight=8))
```

Every call still gets its own result or error, and keeps its own timeout. Calls
sharing a batch share its request, though: if the request itself fails - the
network, a body too large for a proxy in front of Centrifugo - every call in it
fails. A smaller `max_in_flight` batches more; 8 suits most applications.

A batch belongs to no single caller: it runs in a context of its own, which
carries no caller's `contextvars`. `batch_context` makes it one from the
callers' contexts - for a tracing span linking each caller's span:

```python
def batch_context(callers: list[contextvars.Context]):
    links = [trace.Link(c.run(trace.get_current_span).get_span_context()) for c in callers]
    return tracer.start_as_current_span("cent batch", links=links)


client = cent.Client(endpoint, api_key=key, auto_batch=cent.AutoBatch(max_in_flight=8), batch_context=batch_context)
```

## Authentication

`api_key` is sent in the `X-API-Key` header. `bearer_token_func` instead sends a
token as `Authorization: Bearer`, for Centrifugo PRO's JWKS authentication - it
is called for every request, so return a cached token. Leave both unset when
mutual TLS, set up in `http_client`, or a proxy authenticates instead.

To sign the tokens yourself, `token.APITokens` issues them and reuses each for
half its lifetime:

```python
from cent import token

api_tokens = token.APITokens(
    key=api_key,  # its own key - never one of the client tokens
    claims=token.APIClaims(audience="centrifugo-api", scope=["centrifugo:api"]),
)
client = cent.Client("https://centrifugo.example.com/api", bearer_token_func=api_tokens.token)
```

Centrifugo PRO accepts a token signed with any key of `http_api.jwks.endpoint`,
and checks the audience, issuer and scope only when configured to. So keep API
tokens apart from the connection and subscription tokens your users hold - or
any user can call the server API with their connection token:

- publish the API keys with `endpoints.JWKS(*api_keys)` at an endpoint of
  their own, not the one of `client.token.jwks_public_endpoint`;
- set `http_api.jwks.audience` and `http_api.jwks.scope` to values only API
  tokens carry - `token.api` refuses claims with neither.

The API keys rotate as client keys do: see [Key rotation with JWKS](#key-rotation-with-jwks).

Rejected credentials make every call raise `cent.UnauthorizedError`.

## HTTP client, tracing and metrics

cent sends requests with [httpx2](https://pypi.org/project/httpx2/), the
maintained fork of httpx: the same API, imported as `httpx2`. Without
`http_client`, a client keeps up to 256 connections to a host alive, never
follows redirects, and closes idle connections after 50 seconds. A client you
pass - an `httpx2.Client`, or `httpx2.AsyncClient` for `AsyncClient` - is used
as it is, and never changed: credentials and headers go on each request. An
`httpx.Client` is refused, with the fix. Tracing comes from the HTTP client -
with OpenTelemetry (opentelemetry-instrumentation-httpx 0.65b0 or newer):

```python
import httpx2
from opentelemetry.instrumentation.httpx import HTTPX2ClientInstrumentor

http = httpx2.Client(limits=httpx2.Limits(max_connections=256, max_keepalive_connections=256))
HTTPX2ClientInstrumentor.instrument_client(http)
client = cent.Client(endpoint, api_key=key, http_client=http)
```

`on_request` is told of every request - method, commands and how many failed,
duration, status, error - for metrics without a dependency of cent's.

## Shutdown

`client.close()` - `await client.aclose()` - refuses new calls with
`ClosedError` and waits for the ones in progress, automatic batches included,
so that what was accepted is sent before the process exits. With `timeout` it
raises `CentTimeoutError` when calls are still in progress then. Both clients
are context managers which close themselves.

## HTTP handlers

The proxy handlers and the endpoints client SDKs call have a framework-free
core - `handler.handle(method, headers, body)`, `await handler.ahandle(...)` -
and serve as an ASGI app, `handler.asgi`, and a WSGI app, `handler.wsgi`. Their
functions may be blocking or async; under ASGI a blocking one runs in a thread.
Each function receives a `cent.HTTPRequest`: the method, headers, query and the
server's own request object in `raw` - the ASGI scope or the WSGI environ.

```python
# FastAPI, Starlette
app.mount("/centrifugo/connect", connect_handler.asgi)

# Flask
from werkzeug.middleware.dispatcher import DispatcherMiddleware

app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {"/centrifugo/connect": connect_handler.wsgi})

# Django, in urls.py
from django.views.decorators.csrf import csrf_exempt


def django_view(handler):
    @csrf_exempt
    def view(request):
        res = handler.handle(request.method, request.headers, request.body, query=request.GET.dict(), raw=request)
        return HttpResponse(res.body, status=res.status, headers=dict(res.headers))

    return view


urlpatterns = [path("centrifugo/connect", django_view(connect_handler))]
```

Mounted as an ASGI or WSGI app, a handler runs outside your framework's
routing, so its function sees the request's headers but not, say, a FastAPI
dependency. To use your framework's authentication, call the core from a route
of your own, as the Django view does, and hand the function what it needs in
`raw`:

```python
@app.post("/centrifugo/connect")
async def connect(request: Request, user: User = Depends(current_user)) -> Response:
    res = await connect_handler.ahandle(request.method, request.headers, await request.body(), raw=user)
    return Response(res.body, status_code=res.status, headers=dict(res.headers))
```

## Proxy

`cent.proxy` is the backend side of Centrifugo's HTTP proxy, which calls your
application when a client connects, subscribes, publishes or makes an RPC
call: a handler per proxy type, taking a function.

```python
from cent import proxy


def subscribe(request: cent.HTTPRequest, req: proxy.SubscribeRequest) -> proxy.SubscribeResult:
    if not can_read(req.user, req.channel):
        raise proxy.ProxyError(403, "permission denied")
    return proxy.SubscribeResult()


subscribe_handler = proxy.SubscribeHandler(subscribe, on_error=log_proxy_error)
```

Return a result to accept the request, raise `proxy.ProxyError` to reject it
with an error the client receives, or `proxy.Disconnect` to close the client's
connection; any other exception fails the request, and goes to `on_error` to
be logged. Keep proxy endpoints reachable by Centrifugo only: whoever can call
them can claim to be any user.

## Tokens

`cent.token` issues the JWTs Centrifugo authenticates clients with -
connection and subscription tokens, with Centrifugo's claims, signed with
HMAC, RSA, ECDSA or Ed25519 - and `cent.endpoints` serves the endpoints the
`getToken` callbacks of client SDKs call:

```python
from datetime import UTC, datetime, timedelta
from cent import endpoints, token

key = token.Key.hmac(secret)  # client.token.hmac_secret_key


def issue(request: cent.HTTPRequest) -> str:
    user = session_user(request)
    if user is None:
        raise endpoints.Unauthorized  # 403: the client stops asking
    return token.connection(key, token.ConnectionClaims(user=user, expires_at=datetime.now(UTC) + timedelta(hours=1)))


connection_token = endpoints.ConnectionToken(issue, on_error=log_error)
```

An expiry is required: an aware `datetime`, or `token.NEVER` for a token
accepted forever. `endpoints.SubscriptionToken` serves subscription tokens the
same way, with the channel the client asks for. To rotate keys without
restarting Centrifugo, see [Key rotation with JWKS](#key-rotation-with-jwks).

## Key rotation with JWKS

By default Centrifugo verifies tokens with a single key from its
configuration: `client.token.hmac_secret_key`, or an RSA, ECDSA or Ed25519
public key. Changing that key means restarting Centrifugo, and from that
moment it refuses every token signed with the old key. To rotate keys without
that, your application can serve the keys itself, as a JSON Web Key Set (JWKS)
at Centrifugo's `client.token.jwks_public_endpoint`. Each key in the set has an
ID, and Centrifugo verifies a token with the key its `kid` header names:

```python
from pathlib import Path
from cent import endpoints, token

# An ID for each key, never reused for another key: Centrifugo caches keys by ID.
key = token.Key.from_pem(Path("keys/2026-10.pem").read_bytes()).with_key_id("2026-10")

jwks = endpoints.JWKS(key)  # served at the URL of jwks_public_endpoint
tok = token.connection(key, token.ConnectionClaims(user="42", expires_at=expires_at))
```

```json
{"client": {"token": {"jwks_public_endpoint": "https://app.example.com/centrifugo/jwks"}}}
```

Only RSA, ECDSA and Ed25519 keys can go in a set (`pip install cent[crypto]`).
An HMAC secret has no public part to publish. Once `jwks_public_endpoint` is
set, Centrifugo verifies tokens with the set only, and refuses tokens signed
with the key it was configured with before. So moving to a JWKS is a
one-time restart.

How Centrifugo reads the set:

- when a token names a key ID Centrifugo doesn't know, it fetches the set
  again, at most once every 5 seconds;
- it keeps the keys it fetched for 5 minutes (an hour before Centrifugo
  v6.10.2), so a key dropped from the set stops working within that time;
- when the endpoint can't be reached, it keeps using the keys it already has;
- a token whose key isn't in the set is refused as expired, and the client
  SDK asks for a new token.

Rotate a key in three steps. Each step is one deploy of your application, and
every instance should finish a step before any instance moves to the next:

1. **Publish the new key alongside the current one,** and keep signing with
   the current one: `endpoints.JWKS(current, new)`.
2. **Sign with the new key.** Centrifugo fetches the set the first time it
   sees the new ID.
3. **Drop the old key** once every token it signed has expired: wait longer
   than the longest `expires_at` you give.

If a key leaks, do all three steps now, without waiting in step 3. Within
5 minutes Centrifugo refuses new connections with the leaked key's tokens.
Clients that connected before stay connected until their tokens expire:
disconnect them with the server API if needed.

Centrifugo PRO's API tokens rotate the same way, from a set of their own at
`http_api.jwks.endpoint` (see [Authentication](#authentication)).
`token.APITokens(current_key=...)` takes the key to sign with from a
function, so it can switch to the new key at step 2. Each API token is reused
for half its `ttl`, so in step 3 wait at least `ttl` after the switch.

## Shared poll signatures

Clients tracking keys of a [shared poll](https://centrifugal.dev/docs/server/shared_poll)
channel need a signature from the backend. `cent.sharedpoll.sign` makes one,
and `endpoints.SharedPollSignature` serves the endpoint a subscription's
`getSignature` callback calls:

```python
from cent import sharedpoll


def sign(request: cent.HTTPRequest, channel: str, keys: list[str]) -> tuple[list[str], str]:
    allowed = readable(user, channel, keys)  # the rest are revoked
    return allowed, sharedpoll.sign(
        secret, user=user, channel=channel, keys=allowed, expires_at=datetime.now(UTC) + timedelta(hours=1)
    )


signature = endpoints.SharedPollSignature(sign)
```

Shared poll subscriptions are experimental in Centrifugo, and the module
follows their changes.

## Commands for async consumers

`cent.command.publish(...)` - and a method like it for every API method -
checks a request as a client would and encodes it,
for Centrifugo's [async consumers](https://centrifugal.dev/docs/server/consumers):
its `method` and `payload` for an outbox table, or `to_json()` for a Kafka
message.

```python
cmd = cent.command.publish(channel="news", data={"text": "hi"})
cur.execute("INSERT INTO centrifugo_outbox (method, payload, partition) VALUES (%s, %s, 0)", (cmd.method, cmd.payload))
```

A consumer keeps commands in order only within a partition: to keep a
channel's commands in order, derive their partition from the channel the same
way in every writer.

## Streaming AI output

Publish a model's output into a channel of its own, in a namespace with history
and recovery, from one task - each publish waiting for the previous one - in
chunks of what arrived every 50 ms or so, not a publication per token. See
[Centrifugo for AI apps](https://centrifugal.dev/docs/getting-started/ai_apps),
which also covers sizing history for a whole response.

## More

- [API.md](API.md): the API reference, every class, function and field, made
  from the docstrings by `make docs`.
- Docs for agents and LLMs: [centrifugal.dev/llms.txt](https://centrifugal.dev/llms.txt),
  an index of the current (v6) documentation.
- Development: see [AGENTS.md](AGENTS.md); `make check` runs what CI does but
  the integration tests, `make test-integration` those.

MIT license. Centrifugo PRO, which the methods marked "Centrifugo PRO only"
call, is commercial software under its own
[license](https://centrifugal.dev/license).
