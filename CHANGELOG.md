v6.0.0
======

cent 6 is a rewrite of the Python SDK for Centrifugo's HTTP server API to the [Centrifugo server SDK specification](https://github.com/centrifugal/gocent/blob/master/spec.md), version 0.3. It needs Python 3.11 or newer; httpx2 - the maintained fork of httpx - is its only dependency, and `cryptography` 49 or newer is optional, for RSA, ECDSA and Ed25519 tokens (`pip install cent[crypto]`). It works with Centrifugo v6 and Centrifugo PRO v6: the map and shared poll methods need Centrifugo v6.8.0 or newer, `ApiError.temporary` and `TooManyRequestsError` v6.10.0 or newer. Upgrading from cent 5: see the [migration guide](https://github.com/centrifugal/pycent/blob/master/MIGRATING.md).

**Client and calls**

* `Client` and `AsyncClient`, with the same methods, options and errors. Create one per process - an `AsyncClient` per event loop - and share it: both are safe for concurrent use. An `AsyncClient` used from a second event loop raises `InvalidConfigError`; a `Client` in a forked process starts its own connections.
* Every API method of Centrifugo and Centrifugo PRO - the map and shared poll methods included - generated from Centrifugo's `api.proto` with its documentation. A method takes its request's fields as keyword-only arguments, `client.publish(channel="news", data=...)`, and returns a dataclass; no pydantic. A misspelled field raises `TypeError`.
* A field the protos mark required is a required keyword argument, of the method and of a nested type alike - `cent.DeviceTopicsUpdate(op=...)` - and is checked for a value before sending: given empty, `channel=""` or a nested message with nothing set, it raises `InvalidRequestError` naming its path, such as `limit_strategy.rate_limit.policies[0].rate`. A payload set to JSON null, `cent.RawJSON("null")`, is a value. Fields whose empty value means something are sent empty: `invalidate_user_tokens(user="")`, `user_topic_update(user="")`.
* Zero values are not sent, nor is a nested message with nothing set. `device_update`'s `user_update`, `timezone_update`, `locale_update` and `meta_update` are sent whenever set, even empty: `cent.DeviceUserUpdate(user="")` detaches the devices from their user, an empty timezone, locale or meta clears it, and `None` changes nothing.
* `BoolValue` fields are `bool | None`: `None` leaves the server's setting alone.
* Options: `api_endpoint` or `api_endpoint_func`, `api_key` or `bearer_token_func`, `http_client`, `request_timeout`, `headers`, `on_request`, `auto_batch`, `batch_context`. Each is checked at creation, `InvalidConfigError` naming the option and the fix.
* `api_endpoint_func` and `bearer_token_func` are called per request, and may be coroutine functions on `AsyncClient`. An endpoint failing `api_endpoint`'s rules, or an empty token or one with control characters, fails the call with `InvalidConfigError` before sending. An exception either function raises fails the call with `FunctionError`, naming the function, the exception chained as its cause.
* Requests are `POST`s to `{api_endpoint}/{method}`. Redirects are not followed: a redirect is an `HTTPError` with a hint to check the scheme and the path of `api_endpoint`. A caller's `http_client` is never changed: credentials and headers go on each request.
* `close()` and `aclose()` refuse new calls with `ClosedError` and wait for those in progress, automatic batches included; both clients are context managers.
* `cent.to_dict` renders results, commands and errors as JSON-ready data with Centrifugo's field names.

**Constants**

* A constant per value of the string fields with a fixed set, named as the specification pins them for every SDK: `cent.PROVIDER_FCM`, `cent.PLATFORM_IOS`, `cent.OP_ADD`, `cent.STATUS_DELIVERED`, `cent.KEY_MODE_IF_NEW`, `cent.FILTER_NODE_OP_AND`, `cent.CMP_EQ`, and in `cent.proxy` `PROTOCOL_JSON`, `ENCODING_BINARY`, `ALLOW_SUB`, `CAPABILITY_MATCH_WILDCARD`, `CHANNEL_EVENT_TYPE_OCCUPIED`, `KEY_MODE_IF_NEW`, `FILTER_NODE_OP_AND`, `CMP_EQ`. The fields stay strings: a value without a constant is still sent.

**Errors**

* `CentError` is the base of every exception. `ApiError` (`code`, `message`, `temporary`) is raised as the subclass of its code when known - `UnknownChannelError`, `BadRequestError`, `NotFoundError`, `NotAvailableError`, `TooManyRequestsError`, `UnrecoverablePositionError`, `InternalError`... - and as `ApiError` otherwise. Centrifugo's transport error mode gives the same errors.
* `HTTPError` (`status_code`, `body`, `headers`), with `UnauthorizedError` for refused credentials; `DecodeError` for a reply which is not Centrifugo's; `NetworkError`; `CentTimeoutError`, also a builtin `TimeoutError`; `InvalidRequestError` for a request the client can tell is wrong, never sent; `InvalidConfigError` for a client refused as configured - at creation, or on a call; `FunctionError`; `ClosedError`.
* Messages carry hints: a 404 says whether `api_endpoint` lacks the API prefix or the server is Centrifugo OSS answering a PRO method.

**Retries and idempotency**

* `cent.retryable(err)` says whether a new attempt may succeed: a temporary `ApiError`, a network failure, a timeout, a 429 or 5xx; a `FunctionError` by the exception it wraps. Retry a publication only with the same `idempotency_key`: the memory, Redis and PostgreSQL brokers keep keys, five minutes by default; the NATS broker ignores them.
* `broadcast_with_retry` retries only the channels which may still succeed, with one `idempotency_key` for every attempt - made for the call when none is given - and returns every channel's last outcome. `on_attempt_error` returns the wait, and raises to stop; `cent.exponential_backoff` makes waits.

**Broadcast and batch**

* A call raises unless it did everything asked. A broadcast or batch in which some parts failed raises `BroadcastFailedChannelsError` or `BatchFailedCommandsError`: its `failed` lists the failed parts, each with its error, and its `result` holds every part's outcome. One which failed as a whole raises that error, and each command of a batch resolves to it.
* `client.new_batch(parallel=...)`: a method per API method, each returning a `Pending` whose `result()` is that command's result or raises its error; `send()` sends them in one request. An invalid command fails the batch before sending, naming its index; a command added to a sent batch is refused.

**Automatic batching**

* `auto_batch=cent.AutoBatch(max_in_flight=..., max_batch_size=...)`: below `max_in_flight` requests in flight every call goes out at once, alone; at the cap, calls queue and go out together in one `/api/batch` request when a request finishes. Every call gets its own result or error and keeps its own deadline. `batch_context` carries callers' `contextvars` - a tracing span, say - to the batch's request.

**Timeouts**

* `request_timeout`, ten seconds by default, bounds every call: connecting, each read and write, and the reply's body, checked as it arrives. A call's `timeout` replaces it for that call, longer or shorter; 0 is refused, as a negative is - `None` means `request_timeout`. An enclosing `asyncio.timeout`, or cancelling the task, only ends a call sooner. A blocking call can outlast its timeout only while a server sends the reply's headers a few bytes at a time; `AsyncClient` bounds the whole call.
* `broadcast_with_retry`: `timeout` bounds the whole call, waits included; `attempt_timeout` is each attempt's own timeout, replacing `request_timeout` for it, while `timeout` still ends an attempt sooner.
* An automatic batch request lasts until the latest deadline of its calls, and at least `request_timeout` from when it is sent.

**Pages and positions**

* `history_all`, `device_list_all`, `device_topic_list_all`, `user_topic_list_all` and `map_read_state_all` return the items of every page - a generator on `Client`, an async iterator on `AsyncClient` - reading a page when the loop reaches it. They take no per-call `timeout`: `page_timeout` bounds each page's request in place of `request_timeout`.
* `history_all` yields `cent.HistoryItem`s - each a `Publication` with `position()` to resume from - and refuses a `limit` below 1 and `reverse` at the call. `map_read_state_all` yields `cent.MapStateItem`s - each a `MapEntry` with `state`, the position the state was read at - and reads every page after the first at the first one's revision, so that a map reset between pages raises `UnrecoverablePositionError`.
* `position()`, a `StreamPosition`, on the results of `publish`, `history`, `map_read_state`, `map_read_stream`, `map_publish` and `map_remove`: `client.history(channel=..., since=res.position())` reads what came after a publication.

**Payloads**

* `data`, `info`, `meta` and the other payloads are native JSON values or `cent.RawJSON`, sent as the same JSON value - raw JSON's number text kept. A `str` is a JSON string. NaN, infinities, bytes and invalid raw JSON raise `InvalidRequestError` before sending. A payload from a reply sent back unchanged is the same JSON value.

**Tokens and JWKS**

* `cent.token`: connection and subscription tokens - `token.connection`, `token.subscription` with `ConnectionClaims` and `SubscriptionClaims`, the `profile` claim included - signed with `token.Key` HMAC, RSA, ECDSA (P-256, P-384, P-521) or Ed25519 keys. An expiry is required: an aware `datetime`, or `token.NEVER`. `token.jwks` and `endpoints.JWKS` publish public keys for rotation without restarting Centrifugo.

**API tokens**

* `token.api` signs Centrifugo PRO server API tokens with `APIClaims`; `token.APITokenSource` issues them and reuses each for half its lifetime - its `token` method is a client's `bearer_token_func`.

**Endpoints for client SDKs**

* `cent.endpoints.ConnectionToken`, `SubscriptionToken` and `SharedPollSignature`: the endpoints client SDKs' `getToken` callbacks call. `endpoints.Forbidden` answers 403, which client SDKs report as their `UnauthorizedError` - not `cent.UnauthorizedError`, Centrifugo refusing this server's credentials.

**Shared poll**

* `cent.sharedpoll.sign` signs shared poll subscriptions, its expiry required: a datetime, or `token.NEVER`.

**Proxy handlers**

* `cent.proxy`: a handler per proxy type - connect, refresh, subscribe, publish, RPC, sub refresh, map publish, map remove, shared poll refresh, channel state and cache empty - with the requests and results generated from Centrifugo's `proxy.proto`. A function returns a result, or raises `proxy.ProxyError` or `proxy.Disconnect`; anything else is a 500 reported to `on_error`.

**HTTP handlers**

* The proxy handlers and the endpoints have a framework-free core, `handle` and `ahandle`, and serve as ASGI and WSGI apps; their functions may be blocking or async.

**Commands for async consumers**

* `cent.command.publish(...)` and a method like it for every API method check a request as a call does and encode it, for Centrifugo's [async consumers](https://centrifugal.dev/docs/server/consumers): `method` and `payload` for an outbox table, `to_json()` for a whole-command message.

**Observability**

* `on_request` is called after every HTTP request with a `RequestInfo` - method, commands, how many failed, duration, status, error - for metrics. Tracing comes from the HTTP client, such as OpenTelemetry's httpx2 instrumentation.

**Testing helpers**

* `Pending.resolved`, and public constructors of the results and of `BroadcastFailedChannelsError` and `BatchFailedCommandsError`, make test doubles; the README shows a fake transport answering `publish`, `broadcast` and a batch.

v4.1.0
======

* Fix `offset` field in history result which previously contained `publications`, [#24](https://github.com/centrifugal/cent/issues/24).

v4.0.1
======

Upload on Pypi with wheel.

v4.0.0
======

New major release to work with Centrifugo v3

* Client does not add `/api` suffix automatically, developers now need to provide full Centrifugo HTTP API endpoint address explicitly
* Drop Python 2 support

3.0.1
=====

* fix history API method call

3.0.0
=====

* new major release to work with Centrifugo v2

2.1.0
=====

* use `requests.Session` and allow to provide custom session to client initialization via `session` kwarg.

For example to provide custom Session:

```python
import requests

sess = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=5, pool_maxsize=5)
sess.mount("https://", adapter)

client = Client("https://centrifugo.example.com", "secret", session=sess)
```

2.0.2
=====

* `verify` boolean `Client` initialization option (default: `True`). When `False` disables SSL certificate
    verification.
* `get_timestamp` helper function to get current timestamp seconds string value as required by Centrifugo.

2.0.1
=====

* Wrap wrong status code in RequestException
* Fix preparing API endpoint url

2.0.0
=====

Cent client now uses `requests` lib internally to make requests to Centrifugo. Also it's now
more pythonic because it does not return exceptions but raises them. It breaks the old API so
this is a new major release. See updated readme.

1.3.0
=====

* add `broadcast` API command support


1.2.0
=====

* add `insecure_api` boolean option to `Client` - when `True` then client
    won't generate sign for every request to Centrifugo. This will work when Centrifugo
    itself started with `--insecure_api` option. Don't forget about firewall rules in production.


1.1.0
=====

Some improvements in cent public API here.

`publish`, `unsubscribe`, `disconnect` helper methods now return just an error if any error occurred.

`presence`, `history`, `stats`, `channels` helper methods now return data requested and error
(instead of full response and error). `error` field of response now wrapped in `ResponseError`
exception. This means that now you don't need to extract response body and then data from it and
check response error manually in your code every time you use methods above.

For example see calling `stats` method:

```python
from cent.core import Client

client = Client("http://localhost:8000", "secret")

stats, error = client.stats()
if error:
    # error occurred, handle it in a way you prefer.
    raise error

print stats
```

Compare with code required before to do the same:

```python
from cent.core import Client

client = Client("http://localhost:8000", "secret")

resp, error = client.stats()
if error:
    # error occurred, handle it
    raise error
if resp["error"]:
    # handle response error
    raise Exception(resp["error"])

stats = resp["body"]["data"]
print stats
```

I.e. here is how to use helper methods:

```python
from cent.core import Client

client = Client("http://localhost:8000", "secret")

error = client.publish("public:chat", {"input": "test"})
error = client.unsubscribe("user_id_here")
error = client.disconnect("user_id_here")
messages, error = client.history("public:chat")
clients, error = client.presence("public:chat")
channels, error = client.channels()
stats, error = client.stats()
```

Low level sending over calling `add` method not affected in this release.


1.0.0
=====

* support for Centrifugo 1.0.0

This means that no more project key required.

How to migrate
--------------

Omit project key when instantiating Client:

```
from cent.core import Client
client = Client("http://localhost:8000", "project_secret")
```

And also note that token and sign generation function do not accept project key anymore.

0.6.0
=====

* support `channels` command (Centrifugo >= 0.3.0 required)

0.5.0
=====

Added several API methods for client to simplify sending single commands to API.

* `client.publish(channel, data, client=None)`
* `client.presence(channel)`
* `client.history(channel)`
* `client.unsubscribe(user_id, channel=None)`
* `client.disconnect(user_id)`

For example:

```python
from cent.core import Client

client = Client("http://localhost:8000", "development", "secret")

for i in range(1000):
    res, err = client.publish("$public:docs", {"json": True})
    print res
```

0.4.0
=====

Cent 0.4.0 reflects Centrifuge 0.8.0 changes. Centrifuge 0.8.0 uses project name as API key instead of project ID

* update console client configuration file option names (see below)
* empty string (`""`) instead of empty object `"{}"` for default `info`


How to migrate
==============

* use project key (project name) instead of project ID when creating `Client` instance
* use `key` instead of `project_id` in console tool configuration file
* use `secret` instead of `secret_key` in console tool configuration file

So instead of that:
```
[football]
address = http://localhost:8000/api
project_id = 51b229f778b83c2eced3a76b
secret_key = 994021f2dc354d7893d88b90d430498e
timeout = 5
```

Write this:
```
[football]
address = http://localhost:8000/api
key = football
secret = 994021f2dc354d7893d88b90d430498e
timeout = 5
```


0.3.0
=====

works with Centrifuge >= 0.7.0

* `user_info` kwarg renamed to `info` in `generate_token` method
* new `generate_channel_sign` method to generate auth sign for private channel subscriptions
* use `sha256` hashing algorithm to generate HMACs

0.2.1
=====

* Added `json_encoder` keyword argument to use custom JsonEncoder
