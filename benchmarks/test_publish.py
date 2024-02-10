import random
import pytest

from benchmarks.conftest import BenchmarkDecoratorType
from cent import AsyncClient, Client


def sync_requests(client: Client) -> None:
    channel_number = random.randint(0, 1000)  # noqa: S311
    client.publish(
        channel=f"personal_{channel_number}",
        data={"message": "Hello world!"},
    )


async def async_requests(client: AsyncClient) -> None:
    channel_number = random.randint(0, 1000)  # noqa: S311
    await client.publish(
        channel=f"personal_{channel_number}",
        data={"message": "Hello world!"},
    )


def test_sync(
    aio_benchmark: BenchmarkDecoratorType,
    sync_client: Client,
) -> None:
    @aio_benchmark
    def _() -> None:
        sync_requests(sync_client)


@pytest.mark.anyio()
async def test_async(aio_benchmark: BenchmarkDecoratorType, async_client: AsyncClient) -> None:
    @aio_benchmark
    async def _() -> None:
        await async_requests(async_client)
