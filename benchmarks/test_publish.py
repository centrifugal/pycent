from typing import Union

import pytest

from benchmarks.conftest import BenchmarkDecoratorType
from cent import AsyncClient, Client, GrpcClient


def sync_requests(client: Client) -> None:
    for j in range(1000):
        client.publish(
            channel=f"personal:{j}",
            data={"message": "Hello world!"},
        )


async def async_requests(client: Union[GrpcClient, AsyncClient]) -> None:
    for j in range(1000):
        print(j)
        await client.publish(
            channel=f"personal:{j}",
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
