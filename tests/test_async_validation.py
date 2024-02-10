import pytest

from cent import (
    AsyncClient, CentAPIError, PublishRequest, StreamPosition, Disconnect,
    BroadcastRequest, PresenceRequest)

from tests.conftest import UNKNOWN_CHANNEL_ERROR_CODE


async def test_publish(async_client: AsyncClient) -> None:
    await async_client.publish(
        "personal_1",
        {"data": "data"},
        skip_history=False,
        tags={"tag": "tag"},
        # b64data=b64encode(b"data").decode(),
        idempotency_key="idempotency_key",
    )


async def test_broadcast(async_client: AsyncClient) -> None:
    await async_client.broadcast(
        ["personal_1", "personal_2"],
        {"data": "data"},
        skip_history=False,
        tags={"tag": "tag"},
        # b64data=b64encode(b"data").decode(),
        idempotency_key="idempotency_key",
    )


async def test_subscribe(async_client: AsyncClient) -> None:
    await async_client.subscribe(
        "user",
        "personal_1",
        info={"info": "info"},
        # b64info=b64encode(b"info").decode(),
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
    await async_client.history(
        channel="personal_1",
        limit=1,
        reverse=True,
    )


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
