CENT
====

Python tools to communicate with Centrifugo v5 HTTP API. Python >= 3.9 supported.

To install run:

```bash
pip install cent
```

## Centrifugo compatibility

**Cent v5 and higher works only with Centrifugo v5**.

* If you need to work with Centrifugo v3, v4 then use Cent v4
* If you need to work with Centrifugo v2 then use Cent v3

## Usage

First see [available API methods in documentation](https://centrifugal.dev/docs/server/server_api#api-methods).

This library contains `Client`, `AsyncClient` and `GrpcClient` classes to work with Centrifugo HTTP API.

```python
import asyncio
from cent import AsyncClient, Client

url = "http://localhost:8000/api"
api_key = "XXX"

# Initialize a client (you can use sync or async version)
sync_client = Client(url, api_key=api_key)
async_client = AsyncClient(url, api_key=api_key)

# Now you can use sync client to call API methods.
result = sync_client.publish("example:channel", {"input": "Hello world!"})
print(result)


async def main():
    # And async client to call API methods too.
    result = await async_client.publish("example:channel", {"input": "Hello world!"})
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
```

### Handling errors

This library may raise exceptions if sth goes wrong. All exceptions are subclasses of `cent.CentError`.

* CentError - base class for all exceptions
* CentNetworkError - raised in case of network related errors (connection refused)
* CentTransportError - raised in case of transport related errors (HTTP status code is not 2xx)
* CentTimeoutError - raised in case of timeout
* CentUnauthorizedError - raised in case of unauthorized access
* CentDecodeError - raised in case of server response decoding error
* CentAPIError - raised in case of API error (error returned by Centrifugo itself)

### HTTP client init arguments

Required:

* `api_url` (str) - Centrifugo HTTP API URL address
* `api_key` (str) - Centrifugo HTTP API key

Optional:

* `request_timeout` (float) - base timeout for all requests in seconds, default is 10 seconds.

### GRPC client init arguments

Required:

* `host` (str) - Centrifugo GRPC API host
* `port` (int) - Centrifugo GRPC API port

Optional:

* `request_timeout` (float) - base timeout for all requests in seconds, default is 10 seconds.

## HTTP vs GRPC for payloads

When using HTTP-based clients (`Client` and `AsyncClient`):

* you should pass payload as a Python objects which can be serialized to JSON
* in results, you will receive Python objects already deserialized from JSON.

When using GRPC-based client (`GrpcClient`):

* you must pass payloads as `bytes`
* in results, you will receive `bytes` for payloads

## For contributors

### Tests and benchmarks

To start tests, you can use pytest with any additional options, for example:

```bash
make test
```

To start benchmarks, you can use pytest too, for example:

```bash
make bench
```

### Generate code from proto file, if needed

```bash
make proto
```
