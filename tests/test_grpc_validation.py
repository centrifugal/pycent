import json

import pytest

from cent import (GrpcClient, CentAPIError, StreamPosition,
                  ChannelOptionsOverride, BoolValue, Disconnect)
from tests.conftest import UNKNOWN_CHANNEL_ERROR_CODE


async def test_publish(grpc_client: GrpcClient) -> None:
    await grpc_client.publish(
        "personal_1",
        json.dumps({"data": "data"}).encode(),
        skip_history=False,
        tags={"tag": "tag"},
        # b64data=b64encode(b"data").decode(),
        idempotency_key="idempotency_key",
    )


async def test_broadcast(grpc_client: GrpcClient) -> None:
    await grpc_client.broadcast(
        ["personal_1", "personal_2"],
        json.dumps({"data": "data"}).encode(),
        skip_history=False,
        tags={"tag": "tag"},
        # b64data=b64encode(b"data").decode(),
        idempotency_key="idempotency_key",
    )


async def test_subscribe(grpc_client: GrpcClient) -> None:
    await grpc_client.subscribe(
        "user",
        "personal_1",
        info=json.dumps({"info": "info"}).encode(),
        # b64info=b64encode(b"info").decode(),
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
    await grpc_client.history(
        channel="personal_1",
        limit=1,
        reverse=True,
    )


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
