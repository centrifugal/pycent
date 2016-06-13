CENT
====

Python tools to communicate with Centrifugo HTTP API. Python 2.6, Python 2.7 and Python >= 3.3 supported.

To install run:

```bash
pip install cent
```

### High-level library API

First see [available API methods in documentation](https://fzambia.gitbooks.io/centrifugal/content/server/api.html).

This library contains `Client` class to send messages to Centrifugo from your python-powered backend:

```python
from cent.core import Client

url = "http://localhost:8000"
secret_key = "secret"

# initialize client instance.
client = Client(url, secret_key, timeout=1)

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
stats = client.stats()
```

`publish`, `disconnect`, `unsubscribe` return `None` in case of success. Each of this commands can
raise an instance of `CentException`.

I.e.:

```python
from cent.core import Client, CentException

client = Client("http://localhost:8000", "secret", timeout=1)
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

client = Client("http://localhost:8000", "SECRET", timeout=1)

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
[{'error': None, 'body': None, 'method': 'publish'}]
```

I.e. list of single response to each command sent. So you need to inspect response on errors yourself.

### cent as console client

Cent can also be used as console client to communicate with server API.

By default Cent uses `.centrc` configuration file from your home directory (``~/.centrc``).

In this file you must write several settings - server address and project secret. And optionally timeout.

Here is an example of Cent config file content:

```bash
[bananas]
address = http://localhost:8000
secret = long-secret-key-for-bananas-project
timeout = 5
```

The most obvious case of using Cent is broadcasting events into channels.

It is easy enough:

```bash
cent bananas publish --params='{"channel": "news", "data": {"title": "World Cup 2018", "text": "some text..."}}'
```

- **cent** is the name of program
- **bananas** is the name of section in configuration file
- **publish** is the method name you want to call
- **--params** is a JSON string with method parameters, in case of publish you should provide channel and data parameters.




