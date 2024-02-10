import contextlib
from typing import (
    Any,
    AsyncGenerator,
    Tuple,
    Dict,
    Callable,
    Awaitable,
    Optional,
    cast,
    TYPE_CHECKING,
)

import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from cent import Client, AsyncClient

if TYPE_CHECKING:
    from asyncio import AbstractEventLoop
    from threading import Thread

BASE_URL = "http://localhost:8000/api"
API_KEY = "api_key"

BenchmarkCoroType = Callable[[], Awaitable[None]]
BenchmarkType = Callable[[], Optional[Awaitable[None]]]
BenchmarkDecoratorType = Callable[[BenchmarkType], None]


@pytest.fixture(scope="session")
def anyio_backend() -> Tuple[str, Dict[str, bool]]:
    return "asyncio", {"use_uvloop": True}


@pytest.fixture()
def aio_benchmark(benchmark: BenchmarkFixture) -> BenchmarkDecoratorType:
    import asyncio
    import threading

    class Sync2Async:
        def __init__(self, coro: BenchmarkCoroType) -> None:
            self.coro = coro
            self.custom_loop: Optional["AbstractEventLoop"] = None
            self.thread: Optional["Thread"] = None

        def start_background_loop(self) -> None:
            if self.custom_loop:
                asyncio.set_event_loop(self.custom_loop)
                self.custom_loop.run_forever()

        def __call__(self) -> Any:
            awaitable = self.coro()
            with contextlib.suppress(RuntimeError):
                evloop = asyncio.get_running_loop()
            if evloop is None:
                return asyncio.run(awaitable)
            else:
                if not self.custom_loop or not self.thread or not self.thread.is_alive():
                    self.custom_loop = asyncio.new_event_loop()
                    self.thread = threading.Thread(
                        target=self.start_background_loop,
                        daemon=True,
                    )
                    self.thread.start()

                return asyncio.run_coroutine_threadsafe(awaitable, self.custom_loop).result()

    def _wrapper(func: BenchmarkType) -> None:
        if asyncio.iscoroutinefunction(func):
            func = cast(BenchmarkCoroType, func)
            benchmark(Sync2Async(func))
        else:
            benchmark(func)

    return _wrapper


@pytest.fixture()
def sync_client() -> Client:
    return Client(BASE_URL, API_KEY)


@pytest.fixture()
async def async_client(
    anyio_backend: Any,  # noqa: ARG001
) -> AsyncGenerator[AsyncClient, None]:
    client = AsyncClient(BASE_URL, API_KEY)
    yield client
    await client.session.close()
