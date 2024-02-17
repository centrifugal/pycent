Python SDK to communicate with Centrifugo v5 HTTP API. Python >= 3.9 supported.

To install run:

```bash
pip install cent
```

## Centrifugo compatibility

**Cent v5 and higher works only with Centrifugo v5**.

* If you need to work with Centrifugo v3, v4 => use Cent v4
* If you need to work with Centrifugo v2 => use Cent v3

## Usage

First of all, see the description of Centrifugo [server API](https://centrifugal.dev/docs/server/server_api) in the documentation.

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
from cent import Client

api_url = "http://localhost:8000/api"
api_key = "<CENTRIFUGO_API_KEY>"

client = Client(api_url, api_key)
result = client.publish("channel", {"input": "Hello world!"})
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
from cent import AsyncClient

api_url = "http://localhost:8000/api"
api_key = "<CENTRIFUGO_API_KEY>"

client = AsyncClient(api_url, api_key)

async def main():
    result = await client.publish("channel", {"input": "Hello world!"})
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
* `CentResponseError` - raised in case of API response error (i.e. error returned by Centrifugo itself, you can inspect code and message returned by Centrifugo in this case)

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

* Constructor slightly changed, refer to the examples above.
* Base exception class is now `CentError` instead of `CentException`, exceptions SDK raises were refactored.
* To send multiple commands in one HTTP request SDK provides `batch` method.
