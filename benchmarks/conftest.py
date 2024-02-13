import asyncio
import pytest_asyncio
from typing import (
    AsyncGenerator,
    Callable,
    Awaitable,
    Optional,
)

import pytest

from cent import Client, AsyncClient

API_URL = "http://localhost:8000/api"
API_KEY = "api_key"

BenchmarkCoroType = Callable[[], Awaitable[None]]
BenchmarkType = Callable[[], Optional[Awaitable[None]]]
BenchmarkDecoratorType = Callable[[BenchmarkType], None]


@pytest.fixture()
def sync_client() -> Client:
    return Client(API_URL, API_KEY)


@pytest_asyncio.fixture()
async def async_client(
    # anyio_backend: Any,
) -> AsyncGenerator[AsyncClient, None]:
    client = AsyncClient(API_URL, API_KEY)
    yield client
    await client.close()


# async support for pytest-benchmark
# https://github.com/ionelmc/pytest-benchmark/issues/66
@pytest_asyncio.fixture
def aio_benchmark(benchmark, event_loop):  # type: ignore
    def _wrapper(func, *args, **kwargs):  # type: ignore
        if asyncio.iscoroutinefunction(func):

            @benchmark
            def _():  # type: ignore
                return event_loop.run_until_complete(func(*args, **kwargs))
        else:
            benchmark(func, *args, **kwargs)

    return _wrapper
