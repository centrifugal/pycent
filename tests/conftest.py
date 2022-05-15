import pytest

from cent.async_core import AsyncClient
from cent.core import Client


@pytest.fixture
def sync_client():
    return Client(address="http://localhost:8000/api")


@pytest.fixture
def async_client():
    return AsyncClient(address="http://localhost:8000/api")
