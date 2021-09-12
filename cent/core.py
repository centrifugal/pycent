# coding: utf-8
import urllib.parse as urlparse
import sys
import json
import requests


def to_bytes(s):
    return s.encode("latin-1")


class CentException(Exception):
    """
    Wrapper for all exceptions coming from this library.
    """
    pass


class RequestException(CentException):
    """
    RequestException means that request to Centrifugo API failed in some way.
    This is just a wrapper over RequestException from requests library.
    """
    pass


class ClientNotEmpty(CentException):
    """
    ClientNotEmpty raised when attempting to call single method but internal
    client command buffer is not empty.
    """
    pass


class ResponseError(CentException):
    """
    Raised when response from Centrifugo contains any error as result of API
    command execution.
    """
    pass


class Client(object):
    """
    Core class to communicate with Centrifugo.
    """

    def __init__(self, address, api_key="", timeout=1,
                 json_encoder=None, verify=True,
                 session=None, **kwargs):
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
        self.json_encoder = json_encoder
        self.verify = verify
        self.session = session or requests.Session()
        self.kwargs = kwargs
        self._messages = []

    def add(self, method, params):
        data = {
            "method": method,
            "params": params
        }
        self._messages.append(data)

    def send(self, method=None, params=None):
        if method and params is not None:
            self.add(method, params)
        messages = self._messages[:]
        self._messages = []
        data = to_bytes(
            "\n".join([json.dumps(x, cls=self.json_encoder) for x in messages]))
        response = self._send(self.address, data)
        return [json.loads(x) for x in response.split("\n") if x]

    def _send(self, url, data):
        """
        Send a request to a remote web server using HTTP POST.
        """
        headers = {
            'Content-type': 'application/json'
        }
        if self.api_key:
            headers['Authorization'] = 'apikey ' + self.api_key
        try:
            resp = self.session.post(
                url, data=data, headers=headers, timeout=self.timeout, verify=self.verify)
        except requests.RequestException as err:
            raise RequestException(err)
        if resp.status_code != 200:
            raise RequestException("wrong status code: %d" % resp.status_code)
        return resp.content.decode('utf-8')

    def reset(self):
        self._messages = []

    @staticmethod
    def get_publish_params(channel, data, skip_history=False):
        params = {
            "channel": channel,
            "data": data,
            "skip_history": skip_history,
        }
        return params

    @staticmethod
    def get_broadcast_params(channels, data, skip_history=False):
        params = {
            "channels": channels,
            "data": data,
            "skip_history": skip_history,
        }
        return params

    @staticmethod
    def get_subscribe_params(user, channel, client=None):
        params = {
            "user": user,
            "channel": channel
        }
        if client:
            params["client"] = client
        return params

    @staticmethod
    def get_unsubscribe_params(user, channel, client=None):
        params = {
            "user": user,
            "channel": channel
        }
        if client:
            params["client"] = client
        return params

    @staticmethod
    def get_disconnect_params(user, client=None):
        params = {
            "user": user
        }
        if client:
            params["client"] = client
        return params

    @staticmethod
    def get_presence_params(channel):
        return {
            "channel": channel
        }

    @staticmethod
    def get_presence_stats_params(channel):
        return {
            "channel": channel
        }

    @staticmethod
    def get_history_params(channel, limit=0, since=None, reverse=False):
        params = {
            "channel": channel,
            "limit": limit,
            "reverse": reverse,
        }
        if since:
            params["since"] = {
                "offset": since["offset"],
                "epoch": since["epoch"]
            }
        return params

    @staticmethod
    def get_history_remove_params(channel):
        return {
            "channel": channel
        }

    @staticmethod
    def get_channels_params(pattern=""):
        return {
            "pattern": pattern
        }

    @staticmethod
    def get_info_params():
        return {}

    def _check_empty(self):
        if self._messages:
            raise ClientNotEmpty(
                "client command buffer not empty, send commands or reset client")

    def _send_one(self):
        res = self.send()
        data = res[0]
        if "error" in data and data["error"]:
            raise ResponseError(data["error"])
        return data.get("result")

    def publish(self, channel, data, skip_history=False):
        self._check_empty()
        self.add("publish", self.get_publish_params(
            channel, data, skip_history=skip_history))
        result = self._send_one()
        return result

    def broadcast(self, channels, data, skip_history=False):
        self._check_empty()
        self.add("broadcast", self.get_broadcast_params(
            channels, data, skip_history=skip_history))
        result = self._send_one()
        return result

    def subscribe(self, user, channel, client=None):
        self._check_empty()
        self.add("subscribe", self.get_subscribe_params(
            user, channel, client=client))
        self._send_one()
        return

    def unsubscribe(self, user, channel, client=None):
        self._check_empty()
        self.add("unsubscribe", self.get_unsubscribe_params(
            user, channel, client=client))
        self._send_one()
        return

    def disconnect(self, user, client=None):
        self._check_empty()
        self.add("disconnect", self.get_disconnect_params(user, client=client))
        self._send_one()
        return

    def presence(self, channel):
        self._check_empty()
        self.add("presence", self.get_presence_params(channel))
        result = self._send_one()
        return result["presence"]

    def presence_stats(self, channel):
        self._check_empty()
        self.add("presence_stats", self.get_presence_stats_params(channel))
        result = self._send_one()
        return {
            "num_clients": result["num_clients"],
            "num_users": result["num_users"],
        }

    def history(self, channel, limit=0, since=None, reverse=False):
        self._check_empty()
        self.add("history", self.get_history_params(
            channel, limit=limit, since=since, reverse=reverse))
        result = self._send_one()
        return {
            "publications": result.get("publications", []),
            "offset": result.get("publications", 0),
            "epoch": result.get("epoch", ""),
        }

    def history_remove(self, channel):
        self._check_empty()
        self.add("history_remove", self.get_history_remove_params(channel))
        self._send_one()
        return

    def channels(self, pattern=""):
        self._check_empty()
        self.add("channels", params=self.get_channels_params(pattern=pattern))
        result = self._send_one()
        return result["channels"]

    def info(self):
        self._check_empty()
        self.add("info", self.get_info_params())
        result = self._send_one()
        return result
