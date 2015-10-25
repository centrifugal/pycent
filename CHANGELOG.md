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