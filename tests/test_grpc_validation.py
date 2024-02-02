from base64 import b64encode

import pytest

from cent.client.grpc_client import GrpcClient
from cent.exceptions import APIError
from cent.methods.disconnect_data import Disconnect
from cent.types import StreamPosition, ChannelOptionsOverride, BoolValue
from tests.conftest import UNKNOWN_CHANNEL_ERROR_CODE


async def test_publish(grpc_client: GrpcClient) -> None:
    await grpc_client.publish(
        "personal:1",
        {"data": "data"},
        skip_history=False,
        tags={"tag": "tag"},
        b64data=b64encode(b"data").decode(),
        idempotency_key="idempotency_key",
    )


async def test_broadcast(grpc_client: GrpcClient) -> None:
    await grpc_client.broadcast(
        ["personal:1", "personal:2"],
        {"data": "data"},
        skip_history=False,
        tags={"tag": "tag"},
        b64data=b64encode(b"data").decode(),
        idempotency_key="idempotency_key",
    )


async def test_subscribe(grpc_client: GrpcClient) -> None:
    await grpc_client.subscribe(
        "user",
        "personal:1",
        info={"info": "info"},
        b64info=b64encode(b"info").decode(),
        client="client",
        session="session",
        data={"data": "data"},
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
        channel="personal:1",
        session="session",
        client="client",
    )


async def test_presence(grpc_client: GrpcClient) -> None:
    await grpc_client.presence("personal:1")


async def test_presence_stats(grpc_client: GrpcClient) -> None:
    await grpc_client.presence_stats("personal:1")


async def test_history(grpc_client: GrpcClient) -> None:
    await grpc_client.history(
        channel="personal:1",
        limit=1,
        reverse=True,
    )


async def test_history_remove(grpc_client: GrpcClient) -> None:
    await grpc_client.history_remove(channel="personal:1")


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
        whitelist=["personal:1"],
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
    with pytest.raises(APIError, match="unknown channel") as exc_info:
        await grpc_client.publish(
            "undefined_channel:123",
            {"data": "data"},
        )
        assert exc_info.value.code == UNKNOWN_CHANNEL_ERROR_CODE
