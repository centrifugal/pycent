import uuid
import json
import pytest

from cent import (
    GrpcClient,
    CentAPIError,
    StreamPosition,
    ChannelOptionsOverride,
    BoolValue,
    Disconnect,
)
from tests.conftest import UNKNOWN_CHANNEL_ERROR_CODE


async def test_publish(grpc_client: GrpcClient) -> None:
    result = await grpc_client.publish(
        "personal_1",
        json.dumps({"data": "data"}).encode(),
        skip_history=False,
        tags={"tag": "tag"},
        idempotency_key="idempotency_key",
    )
    assert result.offset


async def test_broadcast(grpc_client: GrpcClient) -> None:
    await grpc_client.broadcast(
        ["personal_1", "personal_2"],
        json.dumps({"data": "data"}).encode(),
        skip_history=False,
        tags={"tag": "tag"},
        idempotency_key="idempotency_key",
    )


async def test_subscribe(grpc_client: GrpcClient) -> None:
    await grpc_client.subscribe(
        "user",
        "personal_1",
        info=json.dumps({"info": "info"}).encode(),
        client="client",
        session="session",
        data=json.dumps({"data": "data"}).encode(),
        recover_since=StreamPosition(
            offset=1,
            epoch="1",
        ),
        override=ChannelOptionsOverride(
            presence=BoolValue(value=True),
            join_leave=BoolValue(value=True),
            force_recovery=BoolValue(value=True),
        ),
    )


async def test_unsubscribe(grpc_client: GrpcClient) -> None:
    await grpc_client.unsubscribe(
        user="user",
        channel="personal_1",
        session="session",
        client="client",
    )


async def test_presence(grpc_client: GrpcClient) -> None:
    await grpc_client.presence("personal_1")


async def test_presence_stats(grpc_client: GrpcClient) -> None:
    await grpc_client.presence_stats("personal_1")


async def test_history(grpc_client: GrpcClient) -> None:
    channel = "personal_" + uuid.uuid4().hex
    for i in range(10):
        await grpc_client.publish(
            channel,
            json.dumps({"data": f"data {i}"}).encode(),
        )
    result = await grpc_client.history(
        channel=channel,
        limit=1,
        reverse=True,
    )
    assert isinstance(result.offset, int)
    assert result.offset > 0
    assert len(result.publications) == 1
    assert result.publications[0].data == b'{"data": "data 9"}'


async def test_history_remove(grpc_client: GrpcClient) -> None:
    await grpc_client.history_remove(channel="personal_1")


async def test_info(grpc_client: GrpcClient) -> None:
    await grpc_client.info()


async def test_channels(grpc_client: GrpcClient) -> None:
    await grpc_client.channels(
        pattern="*",
    )


async def test_disconnect(grpc_client: GrpcClient) -> None:
    await grpc_client.disconnect(
        user="user",
        client="client",
        session="session",
        whitelist=["personal_1"],
        disconnect=Disconnect(
            code=4000,
            reason="reason",
        ),
    )


async def test_refresh(grpc_client: GrpcClient) -> None:
    await grpc_client.refresh(
        user="user",
        client="client",
        session="session",
        expire_at=1,
        expired=True,
    )


async def test_error_publish(grpc_client: GrpcClient) -> None:
    with pytest.raises(CentAPIError, match="unknown channel") as exc_info:
        await grpc_client.publish(
            "undefined_channel:123",
            json.dumps({"data": "data"}).encode(),
        )
        assert exc_info.value.code == UNKNOWN_CHANNEL_ERROR_CODE
