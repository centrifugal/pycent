Python SDK to communicate with Centrifugo v5 HTTP API. Python >= 3.9 supported.

To install run:

```bash
pip install cent
```

## Centrifugo compatibility

* **Cent v5 and higher works with Centrifugo v6 and v5**.
* If you need to work with Centrifugo v3, v4 => use Cent v4
* If you need to work with Centrifugo v2 => use Cent v3

## Usage

First of all, see the description of Centrifugo [server API](https://centrifugal.dev/docs/server/server_api) in the documentation. This library also supports API extensions provided by Centrifugo PRO. In general, refer to [api.proto](https://github.com/centrifugal/centrifugo/blob/master/internal/apiproto/api.proto) Protobuf schema file as a source of truth about all available Centrifugo server APIs. Don't forget that Centrifugo supports both HTTP and GRPC API – so you can switch to GRPC by using `api.proto` file to generate stubs for communication.

This library contains `Client` and `AsyncClient` to work with Centrifugo HTTP server API. Both clients have the same methods to work with Centrifugo API and raise the same top-level exceptions.

## Sync HTTP client

```python
from cent import Client
```

Required init arguments:

* `api_url` (`str`) - Centrifugo HTTP API URL address, for example, `http://localhost:8000/api`
* `api_key` (`str`) - Centrifugo HTTP API key for auth

Optional arguments:

* `timeout` (`float`) - base timeout for all requests in seconds, default is 10 seconds.
* `session` (`requests.Session`) - custom `requests` session to use.

Example:

```python
from cent import Client, PublishRequest

api_url = "http://localhost:8000/api"
api_key = "<CENTRIFUGO_API_KEY>"

client = Client(api_url, api_key)
request = PublishRequest(channel="channel", data={"input": "Hello world!"})
result = client.publish(request)
print(result)
```

## Async HTTP client

```python
from cent import AsyncClient
```

Required init arguments:

* `api_url` (`str`) - Centrifugo HTTP API URL address, for example, `http://localhost:8000`
* `api_key` (`str`) - Centrifugo HTTP API key for auth

Optional arguments:

* `timeout` (`float`) - base timeout for all requests in seconds, default is 10 seconds.
* `session` (`aiohttp.ClientSession`) - custom `aiohttp` session to use.

Example:

```python
import asyncio
from cent import AsyncClient, PublishRequest

api_url = "http://localhost:8000/api"
api_key = "<CENTRIFUGO_API_KEY>"

async def main():
    client = AsyncClient(api_url, api_key)
    request = PublishRequest(channel="channel", data={"input": "Hello world!"})
    result = await client.publish(request)
    print(result)

if __name__ == "__main__":
    asyncio.run(main())
```

## Handling errors

This library raises exceptions if sth goes wrong. All exceptions are subclasses of `cent.CentError`.

* `CentError` - base class for all exceptions
* `CentNetworkError` - raised in case of network related errors (connection refused)
* `CentTransportError` - raised in case of transport related errors (HTTP status code is not 2xx)
* `CentTimeoutError` - raised in case of timeout
* `CentUnauthorizedError` - raised in case of unauthorized access (signal of invalid API key)
* `CentDecodeError` - raised in case of server response decoding error
* `CentApiResponseError` - raised in case of API response error (i.e. error returned by Centrifugo itself, you can inspect code and message returned by Centrifugo in this case)

Note, that `BroadcastRequest` and `BatchRequest` are quite special – since they contain multiple commands in one request, handling `CentApiResponseError` is still required, but not enough – you also need to manually iterate over the results to check for individual errors. For example, one publish command can fail while another one can succeed. For example:

```python
from cent import *

c = Client("http://localhost:8000/api", "api_key")
req = BroadcastRequest(channels=["1", "2"], data={})
c.broadcast(req)
# BroadcastResult(
#   responses=[
#       Response[PublishResult](error=None, result=PublishResult(offset=7, epoch='rqKx')),
#       Response[PublishResult](error=None, result=PublishResult(offset=7, epoch='nUrf'))
#   ]
# )
req = BroadcastRequest(channels=["invalid:1", "2"], data={})
c.broadcast(req)
# BroadcastResult(
#   responses=[
#       Response[PublishResult](error=Error(code=102, message='unknown channel'), result=None),
#       Response[PublishResult](error=None, result=PublishResult(offset=8, epoch='nUrf'))
#   ]
# )
```

I.e. `cent` library does not raise exceptions for individual errors in `BroadcastRequest` or `BatchRequest`, only for top-level response error, for example, sending empty list of channels in broadcast:

```
req = BroadcastRequest(channels=[], data={})
c.broadcast(req)
Traceback (most recent call last):
    ...
    raise CentApiResponseError(
cent.exceptions.CentApiResponseError: Server API response error #107: bad request
```

So this all adds some complexity, but that's the trade-off for the performance and efficiency of these two methods. You can always write some convenient wrappers around `cent` library to handle errors in a way that suits your application.

## Using for async consumers

You can use this library to constructs events for Centrifugo [async consumers](https://centrifugal.dev/docs/server/consumers). For example, to get proper method and payload for async publish:

```python
from cent import PublishRequest

request = PublishRequest(channel="channel", data={"input": "Hello world!"})
method = request.api_method
payload = request.api_payload
# use method and payload to construct async consumer event.
```

## Using Broadcast and Batch

To demonstrate the benefits of using `BroadcastRequest` and `BatchRequest` let's compare approaches. Let's say at some point in your app you need to publish the same message into 10k different channels. Let's compare sequential publish, batch publish and broadcast publish. Here is the code to do the comparison:

```python
from cent import *
from time import time


def main():
    publish_requests = []
    channels = []
    for i in range(10000):
        channel = f"test_{i}"
        publish_requests.append(PublishRequest(channel=channel, data={"msg": "hello"}))
        channels.append(channel)
    batch_request = BatchRequest(requests=publish_requests)
    broadcast_request = BroadcastRequest(channels=channels, data={"msg": "hello"})

    client = Client("http://localhost:8000/api", "api_key")

    start = time()
    for request in publish_requests:
        client.publish(request)
    print("sequential", time() - start)

    start = time()
    client.batch(batch_request)
    print("batch", time() - start)

    start = time()
    client.broadcast(broadcast_request)
    print("broadcast", time() - start)


if __name__ == "__main__":
    main()
```

On local machine, the output may look like this:

```
sequential 5.731332778930664
batch 0.12313580513000488
broadcast 0.06050515174865723
```

So `BatchRequest` is much faster than sequential requests in this case, and `BroadcastRequest` is the fastest - publication to 10k Centrifugo channels took only 60ms. Because all the work is done in one network round-trip. In reality the difference will be even more significant because of network latency.

## For contributors

### Tests and benchmarks

Prerequisites – start Centrifugo server locally:

```bash
CENTRIFUGO_API_KEY=api_key CENTRIFUGO_HISTORY_TTL=300s CENTRIFUGO_HISTORY_SIZE=100 \
CENTRIFUGO_PRESENCE=true CENTRIFUGO_GRPC_API=true ./centrifugo
```

And install dependencies:

```bash
make dev
```

Then to run tests, run:

```bash
make test
```

To run benchmarks, run:

```bash
make bench
```

## Migrate to Cent v5

Cent v5 contains the following notable changes compared to Cent v4:

* Client constructor slightly changed, refer to the examples above.
* To call desired API import and construct a request object (inherited from Pydantic `BaseModel`) and then call corresponding method of client. This should feel very similar to how GRPC is usually structured.
* Base exception class is now `CentError` instead of `CentException`, exceptions SDK raises were refactored.
* To send multiple commands in one HTTP request SDK provides `batch` method.
