import uuid
import pytest

from cent import (
    AsyncClient,
    Client,
    CentApiResponseError,
    PublishRequest,
    BroadcastRequest,
    PresenceRequest,
    StreamPosition,
    Disconnect,
    SubscribeRequest,
    BatchRequest,
    UnsubscribeRequest,
    PresenceStatsRequest,
    HistoryRequest,
    HistoryRemoveRequest,
    InfoRequest,
    ChannelsRequest,
    DisconnectRequest,
    RefreshRequest,
    BatchResult,
    HistoryResult,
)

from tests.conftest import UNKNOWN_CHANNEL_ERROR_CODE


async def test_publish(sync_client: Client, async_client: AsyncClient) -> None:
    request = PublishRequest(
        channel="personal_1",
        data={"data": "data"},
        skip_history=False,
        tags={"tag": "tag"},
        idempotency_key="idempotency_key",
    )
    result = sync_client.send(request)
    assert result.offset

    result = await async_client.send(request)
    assert result.offset


async def test_broadcast(sync_client: Client, async_client: AsyncClient) -> None:
    channels = ["personal_1", "personal_2"]
    request = BroadcastRequest(
        channels=channels,
        data={"data": "data"},
        skip_history=False,
        tags={"tag": "tag"},
        idempotency_key="idempotency_key",
    )
    result = sync_client.send(request)
    assert len(result.responses) == len(channels)

    result = await async_client.send(request)
    assert len(result.responses) == len(channels)


async def test_subscribe(sync_client: Client, async_client: AsyncClient) -> None:
    request = SubscribeRequest(
        user="user",
        channel="personal_1",
        client="client",
        session="session",
        data={"data": "data"},
        recover_since=StreamPosition(
            offset=1,
            epoch="1",
        ),
    )
    sync_client.send(request)
    await async_client.send(request)


async def test_unsubscribe(sync_client: Client, async_client: AsyncClient) -> None:
    request = UnsubscribeRequest(
        user="user",
        channel="personal_1",
        session="session",
        client="client",
    )
    sync_client.send(request)
    await async_client.send(request)


async def test_presence(sync_client: Client, async_client: AsyncClient) -> None:
    request = PresenceRequest(
        channel="personal_1",
    )
    sync_client.send(request)
    await async_client.send(request)


async def test_presence_stats(sync_client: Client, async_client: AsyncClient) -> None:
    request = PresenceStatsRequest(
        channel="personal_1",
    )
    sync_client.send(request)
    await async_client.send(request)


async def test_history(sync_client: Client, async_client: AsyncClient) -> None:
    num_pubs = 10
    channel = "personal_" + uuid.uuid4().hex
    for i in range(num_pubs):
        sync_client.send(
            PublishRequest(
                channel=channel,
                data={"data": f"data {i}"},
            ),
        )

    request = HistoryRequest(
        channel=channel,
        limit=num_pubs,
        reverse=False,
    )

    def check_result(res: HistoryResult) -> None:
        assert isinstance(res.offset, int)
        assert res.offset > 0
        assert len(res.publications) == num_pubs
        assert res.publications[0].data == {"data": "data 0"}

    result = sync_client.send(request)
    check_result(result)

    result = await async_client.send(request)
    check_result(result)


async def test_history_remove(sync_client: Client, async_client: AsyncClient) -> None:
    request = HistoryRemoveRequest(
        channel="personal_1",
    )
    sync_client.send(request)
    await async_client.send(request)


async def test_info(sync_client: Client, async_client: AsyncClient) -> None:
    sync_client.send(InfoRequest())
    await async_client.send(InfoRequest())


async def test_channels(sync_client: Client, async_client: AsyncClient) -> None:
    request = ChannelsRequest(pattern="*")

    sync_client.send(request)
    await async_client.send(request)


async def test_disconnect(sync_client: Client, async_client: AsyncClient) -> None:
    request = DisconnectRequest(
        user="user",
        client="client",
        session="session",
        whitelist=["personal_1"],
        disconnect=Disconnect(
            code=4000,
            reason="reason",
        ),
    )

    sync_client.send(request)
    await async_client.send(request)


async def test_refresh(sync_client: Client, async_client: AsyncClient) -> None:
    request = RefreshRequest(
        user="user",
        client="client",
        session="session",
        expire_at=1,
        expired=True,
    )

    sync_client.send(request)
    await async_client.send(request)


async def test_batch(sync_client: Client, async_client: AsyncClient) -> None:
    request = BatchRequest(
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
        ],
        parallel=True,
    )

    def check_result(res: BatchResult) -> None:
        num_expected_replies = 4
        assert len(res.replies) == num_expected_replies
        assert res.replies[0].offset
        assert res.replies[1].offset
        assert res.replies[2].responses[0].result.offset
        assert res.replies[2].responses[1].result.offset
        assert res.replies[3].presence == {}

    result = sync_client.send(request)
    check_result(result)

    result = await async_client.send(request)
    check_result(result)


async def test_error_publish(sync_client: Client, async_client: AsyncClient) -> None:
    request = PublishRequest(
        channel="undefined:channel",
        data={"data": "data"},
    )

    with pytest.raises(CentApiResponseError, match="unknown channel") as exc_info:
        sync_client.send(request)
    assert exc_info.value.code == UNKNOWN_CHANNEL_ERROR_CODE

    with pytest.raises(CentApiResponseError, match="unknown channel") as exc_info:
        await async_client.send(request)
    assert exc_info.value.code == UNKNOWN_CHANNEL_ERROR_CODE
