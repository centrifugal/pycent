Python SDK to communicate with Centrifugo v5 HTTP API. Python >= 3.9 supported.

To install run:

```bash
pip install cent
```

## Centrifugo compatibility

**Cent v5 and higher works only with Centrifugo v5**.

* If you need to work with Centrifugo v3, v4 then use Cent v4
* If you need to work with Centrifugo v2 then use Cent v3

## Usage

See the description of Centrifugo [server API](https://centrifugal.dev/docs/server/server_api) in documentation.

This library contains `Client`, `AsyncClient` and `GrpcClient` classes to work with Centrifugo HTTP and GRPC server API.

```python
import asyncio
from cent import Client, AsyncClient

api_url = "http://localhost:8000/api"
api_key = "<CENTRIFUGO_API_KEY>"

# Initialize a client (you can use sync or async version)
sync_client = Client(api_url, api_key)
async_client = AsyncClient(api_url, api_key)

# Now you can use sync client to call API methods.
result = sync_client.publish("channel", {"input": "Hello world!"})
print(result)


async def main():
    # And async client to call API methods too.
    result = await async_client.publish("channel", {"input": "Hello world!"})
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
```

For GRPC the usage is slightly different:

```python
import asyncio
import json
from cent import GrpcClient

host = "localhost"
port = 10000

grpc_client = GrpcClient(host, port)

async def main():
    result = await grpc_client.publish(
        "example:channel", json.dumps({"input": "Hello world!"}).encode())
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
```

Note that in GRPC case you must pass payload as `bytes`, see below more details about payloads in HTTP vs GRPC cases.

## Sync HTTP client init arguments

```python
from cent import Client
```

Required:

* `api_url` (str) - Centrifugo HTTP API URL address
* `api_key` (str) - Centrifugo HTTP API key

Optional:

* `request_timeout` (float) - base timeout for all requests in seconds, default is 10 seconds.
* `session` (requests.Session) - custom `requests` session to use.

## Async HTTP client init arguments

```python
from cent import AsyncClient
```

Required:

* `api_url` (str) - Centrifugo HTTP API URL address
* `api_key` (str) - Centrifugo HTTP API key

Optional:

* `request_timeout` (float) - base timeout for all requests in seconds, default is 10 seconds.
* `session` (aiohttp.ClientSession) - custom `aiohttp` session to use.

## GRPC client init arguments

```python
from cent import GrpcClient
```

Required:

* `host` (str) - Centrifugo GRPC API host
* `port` (int) - Centrifugo GRPC API port

Optional:

* `request_timeout` (float) - base timeout for all requests in seconds, default is 10 seconds.

## Payloads in HTTP vs GRPC cases

When using HTTP-based clients (`Client` and `AsyncClient`):

* you should pass payload as a Python objects which can be serialized to JSON
* in results, you will receive Python objects already deserialized from JSON.

When using GRPC-based client (`GrpcClient`):

* you must pass payloads as `bytes`
* in results, you will receive `bytes` for payloads

## Handling errors

This library raises exceptions if sth goes wrong. All exceptions are subclasses of `cent.CentError`.

* `CentError` - base class for all exceptions
* `CentNetworkError` - raised in case of network related errors (connection refused)
* `CentTransportError` - raised in case of transport related errors (HTTP status code is not 2xx)
* `CentTimeoutError` - raised in case of timeout
* `CentUnauthorizedError` - raised in case of unauthorized access
* `CentDecodeError` - raised in case of server response decoding error
* `CentAPIError` - raised in case of API error (error returned by Centrifugo itself)

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

To start tests, run:

```bash
make test
```

To start benchmarks, run:

```bash
make bench
```

### Generate code from proto file, if needed

```bash
make proto
```
