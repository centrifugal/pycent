import pytest

from cent.core import Client, ClientNotEmpty


def test_add(sync_client: Client):
    sync_client.add("info", {})
    assert len(sync_client._messages) == 1


def test_reset(sync_client: Client):
    sync_client.add("info", {})
    assert len(sync_client._messages) == 1
    sync_client.reset()
    assert len(sync_client._messages) == 0


def test_info(sync_client: Client):
    res = sync_client.info()
    assert len(res["nodes"]) == 1


def test_check_empty(sync_client: Client):
    sync_client.add("info", {})

    with pytest.raises(ClientNotEmpty):
        sync_client.info("info", {})


def test_publish(sync_client: Client):
    res = sync_client.publish(channel="public", data={"hello": 1})
    assert res == {}


def test_broadcast(sync_client: Client):
    res = sync_client.broadcast(channels=["public", "public2"], data={"hello": 1}, skip_history=True)
    assert res == {"responses": [{"result": {}}, {"result": {}}]}

    res = sync_client.broadcast(channels=["public", "public2"], data={"hello": 1}, skip_history=False)
    assert res == {"responses": [{"result": {}}, {"result": {}}]}


def test_subscribe(sync_client: Client):
    res = sync_client.subscribe(user="1", channel="public")
    assert res is None


def test_unsubscribe(sync_client: Client):
    res = sync_client.unsubscribe(user="1", channel="public")
    assert res is None


def test_disconnect(sync_client: Client):
    res = sync_client.disconnect(user="1")
    assert res is None


def test_presence(sync_client: Client):
    res = sync_client.presence(channel="public")
    assert res is None


def test_presence_stats(sync_client: Client):
    sync_client.presence_stats(channel="public")


def test_history(sync_client: Client):
    sync_client.history(channel="public")
    sync_client.history(channel="public", reverse=True)


def test_history_remove(sync_client: Client):
    sync_client.history_remove(channel="public")


def test_channels(sync_client: Client):
    res = sync_client.channels()
    assert res == {}
