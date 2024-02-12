import uuid
import pytest

from cent import (
    AsyncClient,
    CentAPIError,
    PublishRequest,
    StreamPosition,
    Disconnect,
    BroadcastRequest,
    PresenceRequest,
)

from tests.conftest import UNKNOWN_CHANNEL_ERROR_CODE


async def test_publish(async_client: AsyncClient) -> None:
    result = await async_client.publish(
        "personal_1",
        {"data": "data"},
        skip_history=False,
        tags={"tag": "tag"},
        idempotency_key="idempotency_key",
    )
    assert result.offset


async def test_broadcast(async_client: AsyncClient) -> None:
    await async_client.broadcast(
        ["personal_1", "personal_2"],
        {"data": "data"},
        skip_history=False,
        tags={"tag": "tag"},
        idempotency_key="idempotency_key",
    )


async def test_subscribe(async_client: AsyncClient) -> None:
    await async_client.subscribe(
        "user",
        "personal_1",
        info={"info": "info"},
        client="client",
        session="session",
        data={"data": "data"},
        recover_since=StreamPosition(
            offset=1,
            epoch="1",
        ),
    )


async def test_unsubscribe(async_client: AsyncClient) -> None:
    await async_client.unsubscribe(
        user="user",
        channel="personal_1",
        session="session",
        client="client",
    )


async def test_presence(async_client: AsyncClient) -> None:
    await async_client.presence("personal_1")


async def test_presence_stats(async_client: AsyncClient) -> None:
    await async_client.presence_stats("personal_1")


async def test_history(async_client: AsyncClient) -> None:
    num_pubs = 10
    channel = "personal_" + uuid.uuid4().hex
    for i in range(num_pubs):
        await async_client.publish(
            channel,
            {"data": f"data {i}"},
        )
    result = await async_client.history(
        channel=channel,
        limit=num_pubs,
        reverse=True,
    )
    assert isinstance(result.offset, int)
    assert result.offset > 0
    assert len(result.publications) == num_pubs
    assert result.publications[0].data == {"data": "data 9"}


async def test_history_remove(async_client: AsyncClient) -> None:
    await async_client.history_remove("personal_1")


async def test_info(async_client: AsyncClient) -> None:
    await async_client.info()


async def test_channels(async_client: AsyncClient) -> None:
    await async_client.channels(
        pattern="*",
    )


async def test_disconnect(async_client: AsyncClient) -> None:
    await async_client.disconnect(
        user="user",
        client="client",
        session="session",
        whitelist=["personal_1"],
        disconnect=Disconnect(
            code=4000,
            reason="reason",
        ),
    )


async def test_refresh(async_client: AsyncClient) -> None:
    await async_client.refresh(
        user="user",
        client="client",
        session="session",
        expire_at=1,
        expired=True,
    )


async def test_batch(async_client: AsyncClient) -> None:
    await async_client.batch(
        commands=[
            PublishRequest(
                channel="personal_1",
                data={"data": "Second data"},
            ),
            PublishRequest(
                channel="personal_2",
                data={"data": "First data"},
            ),
            BroadcastRequest(
                channels=["personal_1", "personal_2"],
                data={"data": "Third data"},
            ),
            PresenceRequest(
                channel="personal_1",
            ),
        ]
    )


async def test_error_publish(async_client: AsyncClient) -> None:
    with pytest.raises(CentAPIError, match="unknown channel") as exc_info:
        await async_client.publish(
            "undefined_channel:123",
            {"data": "data"},
        )
        assert exc_info.value.code == UNKNOWN_CHANNEL_ERROR_CODE
