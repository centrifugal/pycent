import uuid
import pytest

from cent import (
    Client,
    CentAPIError,
    PublishRequest,
    BroadcastRequest,
    PresenceRequest,
    StreamPosition,
    Disconnect,
)

from tests.conftest import UNKNOWN_CHANNEL_ERROR_CODE


def test_publish(sync_client: Client) -> None:
    result = sync_client.publish(
        "personal_1",
        {"data": "data"},
        skip_history=False,
        tags={"tag": "tag"},
        idempotency_key="idempotency_key",
    )
    assert result.offset


def test_broadcast(sync_client: Client) -> None:
    sync_client.broadcast(
        ["personal_1", "personal_2"],
        {"data": "data"},
        skip_history=False,
        tags={"tag": "tag"},
        idempotency_key="idempotency_key",
    )


def test_subscribe(sync_client: Client) -> None:
    sync_client.subscribe(
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


def test_unsubscribe(sync_client: Client) -> None:
    sync_client.unsubscribe(
        user="user",
        channel="personal_1",
        session="session",
        client="client",
    )


def test_presence(sync_client: Client) -> None:
    sync_client.presence("personal_1")


def test_presence_stats(sync_client: Client) -> None:
    sync_client.presence_stats("personal_1")


def test_history(sync_client: Client) -> None:
    num_pubs = 10
    channel = "personal_" + uuid.uuid4().hex
    for i in range(num_pubs):
        sync_client.publish(
            channel,
            {"data": f"data {i}"},
        )

    result = sync_client.history(
        channel=channel,
        limit=num_pubs,
        reverse=False,
    )
    assert isinstance(result.offset, int)
    assert result.offset > 0
    assert len(result.publications) == num_pubs
    assert result.publications[0].data == {"data": "data 0"}


def test_history_remove(sync_client: Client) -> None:
    sync_client.history_remove("personal_1")


def test_info(sync_client: Client) -> None:
    sync_client.info()


def test_channels(sync_client: Client) -> None:
    sync_client.channels(
        pattern="*",
    )


def test_disconnect(sync_client: Client) -> None:
    sync_client.disconnect(
        user="user",
        client="client",
        session="session",
        whitelist=["personal_1"],
        disconnect=Disconnect(
            code=4000,
            reason="reason",
        ),
    )


def test_refresh(sync_client: Client) -> None:
    sync_client.refresh(
        user="user",
        client="client",
        session="session",
        expire_at=1,
        expired=True,
    )


def test_batch(sync_client: Client) -> None:
    sync_client.batch(
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


def test_error_publish(sync_client: Client) -> None:
    with pytest.raises(CentAPIError, match="unknown channel") as exc_info:
        sync_client.publish(
            "undefined_channel:123",
            {"data": "data"},
        )
    assert exc_info.value.code == UNKNOWN_CHANNEL_ERROR_CODE
