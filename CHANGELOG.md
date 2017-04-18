2.1.0
=====

* use `requests.Session` and allow to provide custom session to client initialization via `session` kwarg.

For example to provide custom Session:

```python
import requests

sess = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=5, pool_maxsize=5)
sess.mount('https://', adapter)

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
