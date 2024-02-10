CENT
====

Python tools to communicate with Centrifugo v5 HTTP API. Python >= 3.9 supported.

To install run:

```bash
pip install cent
```

## Centrifugo compatibility

**Cent v5 and higher works only with Centrifugo v5**.

* If you need to work with Centrifugo v3 then use Cent v4
* If you need to work with Centrifugo v2 then use Cent v3

## High-level library API

First see [available API methods in documentation](https://centrifugal.dev/docs/server/server_api#api-methods).

This library contains `Client` and `AsyncClient` class to send messages to Centrifugo from your python-powered backend:

```python
import asyncio
from cent import AsyncClient, Client

url = "http://localhost:8000/api"
api_key = "XXX"

# Initialize a client (you can use sync or async version)
async_client = AsyncClient(url, api_key=api_key)
sync_client = Client(url, api_key=api_key)

response = sync_client.publish("example:channel", {"input": "Hello world!"})
print(response)


async def main():
    response = await async_client.publish("example:channel", {"input": "Hello world!"})
    print(response)


if __name__ == "__main__":
    asyncio.run(main())
```

### Client init arguments

Required:

* base_url - Centrifugo HTTP API endpoint address
* api_key - Centrifugo HTTP API key

Optional:

* session (`BaseSession`) - session to use

You can use `AiohttpSession` or create custom from `BaseSession` class.

Arguments for default session:

Required:

* base_url - Centrifugo HTTP API endpoint address

Optional:

* json_loads — function to load JSON from response body (default is json, but you can use
  orjson, ujson etc.)
* timeout - timeout for requests (default is 10.0)

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
poetry run python -m grpc_tools.protoc -I . --python_betterproto_out=./cent/proto cent/proto/apiproto.proto
```
