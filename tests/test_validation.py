import uuid
from typing import List, cast

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
    UnsubscribeRequest,
    PresenceStatsRequest,
    HistoryRequest,
    HistoryRemoveRequest,
    InfoRequest,
    ChannelsRequest,
    DisconnectRequest,
    RefreshRequest,
    HistoryResult,
    CentResult,
    PublishResult,
    BroadcastResult,
    PresenceResult,
    Response,
    BatchRequest,
)


from tests.conftest import UNKNOWN_CHANNEL_ERROR_CODE


def test_serialization_none() -> None:
    request = PublishRequest(
        channel="personal_1",
        data={"data": None},
    )
    assert request.to_json() == {"channel": "personal_1", "data": {"data": None}}


def test_serialization_batch() -> None:
    requests = [
        PublishRequest(
            channel="personal_1",
            data={"data": "Second data"},
        ),
        PublishRequest(
            channel="personal_2",
            data={"data": "First data"},
        ),
    ]
    batch_request = BatchRequest(
        requests=requests,
    )
    assert batch_request.to_json() == {
        "commands": [
            {"publish": {"channel": "personal_1", "data": {"data": "Second data"}}},
            {"publish": {"channel": "personal_2", "data": {"data": "First data"}}},
        ],
        "parallel": False,
    }


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

    def check_result(res: BroadcastResult) -> None:
        assert len(res.responses) == len(channels)
        resp = res.responses[0]
        assert resp.error is None
        assert resp.result is not None
        assert resp.result.offset

    request = BroadcastRequest(
        channels=channels,
        data={"data": "data"},
        skip_history=False,
        tags={"tag": "tag"},
        idempotency_key="idempotency_key",
    )
    result = sync_client.send(request)
    check_result(result)

    result = await async_client.send(request)
    check_result(result)


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
    def check_result(res: List[CentResult]) -> None:
        num_expected_replies = 4
        assert len(res) == num_expected_replies
        assert cast(PublishResult, res[0]).offset
        assert cast(PublishResult, res[1]).offset
        broadcast_result = cast(BroadcastResult, res[2])
        num_expected_responses = 2
        assert len(broadcast_result.responses) == num_expected_responses
        response_0 = broadcast_result.responses[0]
        response_1 = broadcast_result.responses[1]
        assert isinstance(response_0, Response)
        assert isinstance(response_1, Response)
        assert isinstance(response_0.result, PublishResult)
        assert isinstance(response_1.result, PublishResult)
        assert response_0.result.offset
        assert response_1.result.offset
        assert cast(PresenceResult, res[3]).presence == {}

    requests = [
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

    request = BatchRequest(
        requests=requests,
    )

    result = sync_client.send(request)
    check_result(result.replies)

    result = await async_client.send(request)
    check_result(result.replies)


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
