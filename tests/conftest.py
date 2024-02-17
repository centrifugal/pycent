from typing import (
    Any,
    AsyncGenerator,
    Tuple,
    Dict,
)

import pytest

from cent import Client, AsyncClient

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
async def async_client(
    anyio_backend: Any,  # noqa: ARG001
) -> AsyncGenerator[AsyncClient, None]:
    client = AsyncClient(BASE_URL, API_KEY)
    yield client
    await client._session.close()


@pytest.fixture()
async def clients(
    anyio_backend: Any,  # noqa: ARG001
) -> AsyncGenerator[Any, None]:
    sync_client = Client(BASE_URL, API_KEY)
    async_client = AsyncClient(BASE_URL, API_KEY)
    yield sync_client, async_client
    await async_client.close()
    sync_client.close()
