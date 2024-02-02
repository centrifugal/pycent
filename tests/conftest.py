from typing import (
    Any,
    AsyncGenerator,
    Tuple,
    Dict,
)

import pytest

from cent import Client, AsyncClient, GrpcClient

BASE_URL = "http://localhost:8000/api"
API_KEY = "api_key"
UNKNOWN_CHANNEL_ERROR_CODE = 102


@pytest.fixture(scope="session")
def anyio_backend() -> Tuple[str, Dict[str, bool]]:
    return "asyncio", {"use_uvloop": False}


@pytest.fixture()
def sync_client() -> Client:
    return Client(BASE_URL, API_KEY)


@pytest.fixture()
async def grpc_client(
    anyio_backend: Any,  # noqa: ARG001
) -> AsyncGenerator[GrpcClient, None]:
    client = GrpcClient("localhost", 10000)
    yield client
    client.session.close()


@pytest.fixture()
async def async_client(
    anyio_backend: Any,  # noqa: ARG001
) -> AsyncGenerator[AsyncClient, None]:
    client = AsyncClient(BASE_URL, API_KEY)
    yield client
    await client.session.close()
