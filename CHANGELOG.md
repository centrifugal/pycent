v6.0.0
======

A rewrite to the [Centrifugo server SDK specification](https://github.com/centrifugal/gocent/blob/master/spec.md).
Migrating from cent 5: see [MIGRATING.md](MIGRATING.md).

* Python 3.11 or newer. httpx2 - the maintained fork of httpx - is the only dependency; `cryptography` 49 or newer is optional, for RSA, ECDSA and Ed25519 tokens (`pip install cent[crypto]`).
* Every API method takes its request's fields as keyword arguments - `client.publish(channel="news", data=...)` - on the client, a batch and `cent.command` alike; results are dataclasses. All generated from Centrifugo's `api.proto`, with its documentation: every API method, including the map and shared poll methods and those of Centrifugo PRO. No pydantic.
* `Client` and `AsyncClient` with the same methods, options and errors. One deadline per call - its `timeout`, or `request_timeout` - over connecting, each read and write and the reply's body. Redirects are not followed. A caller's HTTP client is never changed.
* A broadcast or batch in which some parts failed raises `BroadcastFailedChannelsError` or `BatchFailedCommandsError`, carrying every part's outcome. cent 5 returned normally.
* New exceptions: `ApiError` with a subclass per known code, `HTTPError`, `DecodeError`, `InvalidRequestError`, `InvalidConfigError`, `FunctionError`, `NetworkError`, `CentTimeoutError`, `ClosedError`; `retryable()`; hints in messages; Centrifugo's transport error mode.
* Payloads: native values or `RawJSON`, sent as the same JSON value; NaN, infinities and bytes refused before sending; a payload from a reply sent back unchanged is the same JSON value.
* `broadcast_with_retry`, `exponential_backoff`; automatic batching of concurrent calls (`auto_batch`); `on_request` for metrics; `close()` and `aclose()` waiting for calls in progress.
* `cent.command.publish(...)` and the like for Centrifugo's async consumers.
* `cent.token`: connection, subscription and Centrifugo PRO server API tokens (HS256, RS256, ES256/384/512, EdDSA), JWKS, `APITokens`.
* `cent.endpoints`: the token and shared poll signature endpoints client SDKs call, and the JWKS endpoint. `cent.proxy`: a handler for every proxy type, generated from `proxy.proto`. Each is a framework-free core with ASGI and WSGI adapters.
* `cent.sharedpoll.sign` for shared poll signatures, its expiry required: a datetime, or `token.NEVER`.
* Fields the protos mark required are required keyword arguments. `cent.to_dict` renders results and errors with Centrifugo's field names. `Pending.resolved` and the public constructors of results and partial-failure errors make test doubles; the README shows a fake transport.
* An `AsyncClient` used from a second event loop raises `InvalidConfigError`; a `Client` in a forked process starts its own connections.

Spec 0.3:

* `api.proto` and `proxy.proto` from Centrifugo master (centrifugal/centrifugo#1308, #1309, #1310), which no release has yet: they are synced again from a Centrifugo tag before this release. `proxy.ConnectResult` gains `profile`.
* A field the protos mark required is checked for a value before sending, by the client, a batch and `cent.command`: given empty - `channel=""`, a nested message with nothing set - it raises `InvalidRequestError` naming its path, such as `limit_strategy.rate_limit.policies[0].rate`, where Centrifugo used to refuse the call with code 107. A payload set to JSON null, `cent.RawJSON("null")`, is a value. Fields whose empty value has a meaning are sent empty: `invalidate_user_tokens(user="")`, `user_topic_update(user="")`.
* The nested types take their required fields as required keyword arguments: `DeviceTopicsUpdate(op=...)`, `RateLimitPolicy(rate=..., interval_ms=...)`, `PushTimeLimitStrategy(...)`, the push notifications' `message` and `payload`, and the device updates' values - `DeviceUserUpdate(user="")`.
* `device_update`'s `user_update`, `timezone_update`, `locale_update` and `meta_update` are sent whenever set, even empty: an empty one detaches the devices from their user or clears the value, which could not be written before. Any other nested message with nothing set is still not sent.
* Constants for the string fields with a fixed set of values, named as the spec pins them for every SDK: `cent.PROVIDER_FCM`, `cent.PLATFORM_IOS`, `cent.OP_ADD`, `cent.STATUS_DELIVERED`, `cent.KEY_MODE_IF_NEW`, `cent.CMP_EQ`, `cent.FILTER_NODE_OP_AND`, and in `cent.proxy` `FILTER_NODE_OP_AND`, `CMP_EQ`, `PROTOCOL_JSON`, `ENCODING_BINARY`, `ALLOW_SUB`, `CAPABILITY_MATCH_WILDCARD`, `KEY_MODE_IF_NEW`, `CHANNEL_EVENT_TYPE_OCCUPIED`. The fields stay strings.
* `history_all`, `device_list_all`, `device_topic_list_all`, `user_topic_list_all` and `map_read_state_all`: the items of every page, a generator on `Client`, an async iterator on `AsyncClient`. `history_all` yields `cent.HistoryItem`s - each a `Publication` with `position()` to resume from - and refuses a `limit` below 1 and `reverse`; `map_read_state_all` yields `cent.MapStateItem`s - each a `MapEntry` with `state`, the position the state was read at - and reads later pages at the first one's revision.
* `position()`, a `StreamPosition`, on the results of `publish`, `history`, `map_read_state`, `map_read_stream`, `map_publish` and `map_remove`.
* Timeouts: `request_timeout` bounds every call, and a call's `timeout` replaces it, longer or shorter - a `timeout` of 0 is refused, as a negative one is, `None` meaning `request_timeout`; an enclosing `asyncio.timeout` or a cancelled task only shortens a call. `broadcast_with_retry`'s `attempt_timeout` is each attempt's own timeout, replacing `request_timeout`, the call's `timeout` still ending an attempt sooner. An automatic batch request may outlast a call's deadline: it lasts until its calls' latest, at least `request_timeout`.
* `endpoints.Unauthorized` is now `endpoints.Forbidden`: the 403 of the token and shared poll signature endpoints, which client SDKs report as their `UnauthorizedError` - not `cent.UnauthorizedError`, Centrifugo refusing this server's credentials.
* `api_endpoint_func` and `bearer_token_func`: an endpoint failing `api_endpoint`'s rules, or an empty token or one with control characters, fails the call with `InvalidConfigError` before sending; an exception the function raises fails it with `cent.FunctionError`, naming the function, the exception chained as its cause - it propagated as it was before - and `retryable` judging it by that exception.
* `token.ConnectionClaims.profile`: the dictionary compression profile claim (Centrifugo PRO).
* Docs: the redirect hint says Centrifugo's API never redirects a call - check the scheme and the path of `api_endpoint`; a command's payload is written as the JSON itself where the method goes apart; what Centrifugo makes of a proxy response with nothing in it.

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
