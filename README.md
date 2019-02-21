CENT
====

Python tools to communicate with Centrifugo HTTP API. Python 2.6, Python 2.7 and Python >= 3.3 supported.

To install run:

```bash
pip install cent
```

### Centrifugo compatibility

Cent v3.0.0 and higher works only with Centrifugo v2.

If you need to work with Centrifugo v1 then use Cent [v2.1.0](https://github.com/centrifugal/cent/tree/v2.1.0)

### High-level library API

First see [available API methods in documentation](https://centrifugal.github.io/centrifugo/server/api/).

This library contains `Client` class to send messages to Centrifugo from your python-powered backend:

```python
from cent import Client

url = "http://localhost:8000"
api_key = "XXX"

# initialize client instance.
client = Client(url, api_key=api_key, timeout=1)

# publish data into channel
channel = "public:chat"
data = {"input": "test"}
client.publish(channel, data)

# other available methods
client.unsubscribe("USER_ID")
client.disconnect("USER_ID")
messages = client.history("public:chat")
clients = client.presence("public:chat")
channels = client.channels()
stats = client.info()
client.history_remove("public:chat")
```

`publish`, `disconnect`, `unsubscribe`, `history_remove` return `None` in case of success. Each of this commands can
raise an instance of `CentException`.

I.e.:

```python
from cent import Client, CentException

client = Client("http://localhost:8000", api_key="XXX", timeout=1)
try:
    client.publish("public:chat", {"input": "test"})
except CentException:
    # handle exception
```

Depending on problem occurred exceptions can be:

* RequestException – HTTP request to Centrifugo failed
* ResponseError - Centrifugo returned some error on request

Both exceptions inherited from `CentException`.


### Low-level library API:

To send lots of commands in one request:

```python
from cent import Client, CentException

client = Client("http://localhost:8000", api_key="XXX", timeout=1)

params = {
    "channel": "python",
    "data": "hello world"
}

client.add("publish", params)

try:
    result = client.send()
except CentException:
    # handle exception
else:
    print result
```

You can use `add` method to add several messages which will be sent.

You'll get something like this in response:

```bash
[{}]
```

I.e. list of single response to each command sent. So you need to inspect response on errors (if any) yourself.

### Client initialization arguments

Required:

* address - Centrifugo address

Optional:

* api_key - HTTP API key of Centrifugo 
* timeout (default: `1`) - timeout for HTTP requests to Centrifugo
* json_encoder (default: `None`) - set custom JSON encoder
* send_func (default: `None`) - set custom send function
* verify (default: `True`) - when set to `False` no certificate check will be done during requests.
