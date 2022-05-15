import json
from typing import Callable, List, Optional

import httpx

from cent.exceptions import ClientNotEmpty, RequestException, ResponseError
from cent.mixins import ParamsMixin
from cent.utils import check_not_empty_pipeline, to_bytes


class Client(ParamsMixin):
    """
    Core class to communicate with Centrifugo.
    """

    def __init__(
        self,
        address: str,
        api_key: str = "",
        timeout: int = 1,
        verify: bool = True,
        json_encoder: Callable = None,
        json_dumps: Callable = None,
        json_loads: Callable = None,
        session: Callable = None,
        **kwargs
    ):
        """
        :param address: Centrifugo address
        :param api_key: Centrifugo API key
        :param timeout: timeout for HTTP requests to Centrifugo
        :param json_encoder: custom JSON encoder
        :param verify: boolean flag, when set to False no certificate check will be done during requests.
        :param session: custom requests.Session instance
        """

        self.address = address
        self.api_key = api_key
        self.timeout = timeout
        self.session = session or httpx.Client(verify=verify)
        self._prepare_session()
        self.kwargs = kwargs
        self.json_encoder = json_encoder
        self.json_dumps = json_dumps or json.dumps
        self.json_loads = json_loads or json.loads
        self._messages = []

    def _check_empty(self):
        if self._messages:
            raise ClientNotEmpty("client command buffer not empty, send commands or reset client")

    def _prepare_session(self):
        if self.api_key:
            self.session.headers["Authorization"] = "apikey " + self.api_key
        self.session.timeout = self.timeout

    def add(self, method, params):
        data = {"method": method, "params": params}
        self._messages.append(data)

    def send(self, method=None, params=None):
        if method and params is not None:
            self.add(method, params)
        messages = self._messages[:]
        self.reset()
        data = to_bytes("\n".join([self.json_dumps(x, cls=self.json_encoder) for x in messages]))
        response = self._send(self.address, data)
        return [self.json_loads(x) for x in response.split("\n") if x]

    def _send(self, url, data) -> str:
        try:
            resp: httpx.Response = self.session.post(
                url=url,
                data=data,
                timeout=self.timeout,
            )
        except RequestException as err:
            raise RequestException(err)
        if resp.status_code != 200:
            raise RequestException("wrong status code: %d" % resp.status_code)
        return resp.text

    def reset(self):
        self._messages = []

    def _send_one(self) -> Optional[dict]:
        resp_json = self.send()[0]
        if "error" in resp_json:
            raise ResponseError(resp_json["error"])
        return resp_json.get("result", {})

    @check_not_empty_pipeline
    def publish(self, channel: str, data: dict, skip_history: bool = False) -> Optional[dict]:
        self.add(
            method="publish",
            params=self.get_publish_params(channel, data, skip_history=skip_history),
        )
        result = self._send_one()
        return result

    @check_not_empty_pipeline
    def broadcast(self, channels: List[str], data: dict, skip_history: bool = False) -> Optional[dict]:
        self.add(
            method="broadcast",
            params=self.get_broadcast_params(channels, data, skip_history=skip_history),
        )
        result = self._send_one()
        return result

    @check_not_empty_pipeline
    def subscribe(self, user: str, channel: str, client: Optional[str] = None) -> None:
        self.add(
            method="subscribe",
            params=self.get_subscribe_params(user, channel, client=client),
        )
        self._send_one()
        return

    @check_not_empty_pipeline
    def unsubscribe(self, user: str, channel: str, client: Optional[str] = None) -> None:
        self.add(
            method="unsubscribe",
            params=self.get_unsubscribe_params(user, channel, client=client),
        )
        self._send_one()
        return

    @check_not_empty_pipeline
    def disconnect(self, user: str, client: Optional[str] = None) -> None:
        self.add(
            method="disconnect",
            params=self.get_disconnect_params(user, client=client),
        )
        self._send_one()
        return

    @check_not_empty_pipeline
    def presence(self, channel: str) -> dict:
        self.add(
            method="presence",
            params=self.get_presence_params(channel),
        )
        result = self._send_one()
        return result["presence"]

    @check_not_empty_pipeline
    def presence_stats(self, channel: str) -> dict[str, int]:
        self.add(
            method="presence_stats",
            params=self.get_presence_stats_params(channel),
        )
        result = self._send_one()
        return {
            "num_clients": result["num_clients"],
            "num_users": result["num_users"],
        }

    @check_not_empty_pipeline
    def history(self, channel: str, limit: int = 0, since: dict = None, reverse: bool = False) -> dict:
        self.add(
            method="history",
            params=self.get_history_params(channel, limit=limit, since=since, reverse=reverse),
        )
        result = self._send_one()
        return {
            "publications": result.get("publications", []),
            "offset": result.get("offset", 0),
            "epoch": result.get("epoch", ""),
        }

    @check_not_empty_pipeline
    def history_remove(self, channel: str) -> None:
        self.add(
            method="history_remove",
            params=self.get_history_remove_params(channel),
        )
        self._send_one()
        return

    @check_not_empty_pipeline
    def channels(self, pattern="") -> List[Optional[str]]:
        self.add(
            method="channels",
            params=self.get_channels_params(pattern=pattern),
        )
        result = self._send_one()
        return result["channels"]

    @check_not_empty_pipeline
    def info(self) -> dict[str, list]:
        self.add(
            method="info",
            params=self.get_info_params(),
        )
        result = self._send_one()
        return result
