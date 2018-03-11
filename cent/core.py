# coding: utf-8
try:
    import urllib.parse as urlparse
except ImportError:
    import urlparse

import sys
import hmac
import time
import json
from hashlib import sha256
import requests


PY2 = sys.version_info[0] == 2

if not PY2:
    def to_bytes(s):
        return s.encode("latin-1")
else:
    def to_bytes(s):
        return s


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


def generate_client_sign(secret, user, exp, info="", opts=""):
    """
    When client from browser wants to connect to Centrifuge he must send his
    user ID, timestamp and optional info. To validate that data we use HMAC
    SHA-256 to build token.
    @param secret: Centrifugo secret key
    @param user: user ID from your application
    @param exp: current timestamp seconds as string
    @param info: optional json encoded data for this client connection
    @param opts: optional connection options string
    """
    sign = hmac.new(to_bytes(str(secret)), digestmod=sha256)
    sign.update(to_bytes(user))
    sign.update(to_bytes(exp))
    sign.update(to_bytes(info))
    sign.update(to_bytes(opts))
    token = sign.hexdigest()
    return token


def generate_channel_sign(secret, client, channel, info=""):
    """
    Generate HMAC SHA-256 sign for private channel subscription.
    @param secret: Centrifugo secret key
    @param client: client ID
    @param channel: channel client wants to subscribe to
    @param info: optional json encoded data for this channel
    """
    auth = hmac.new(to_bytes(str(secret)), digestmod=sha256)
    auth.update(to_bytes(str(client)))
    auth.update(to_bytes(str(channel)))
    auth.update(to_bytes(info))
    return auth.hexdigest()


def generate_exp_timestamp(lifetime_seconds):
    """
    Returns exp timestamp string required to make connection to Centrifugo.
    @param lifetime_seconds: connection lifetime in seconds.
    """
    return str(int(time.time() + lifetime_seconds))


class Client(object):
    """
    Core class to communicate with Centrifugo.
    """

    def __init__(self, address, api_key="", timeout=1,
                 json_encoder=None, insecure_api=False, verify=True,
                 session=None, **kwargs):
        """
        :param address: Centrifugo address
        :param api_key: Centrifugo API key
        :param timeout: timeout for HTTP requests to Centrifugo
        :param json_encoder: custom JSON encoder
        :param insecure_api: boolean value, when set to True no signing will be used
        :param verify: boolean flag, when set to False no certificate check will be done during requests.
        :param session: custom requests.Session instance
        """

        self.address = address
        self.api_key = api_key
        self.timeout = timeout
        self.json_encoder = json_encoder
        self.insecure_api = insecure_api
        self.verify = verify
        self.session = session or requests.Session()
        self.kwargs = kwargs
        self._messages = []

    def prepare_url(self):
        """
        http(s)://centrifuge.example.com/api/

        Some work here to prepare valid API url: make it work even if following urls provided
        during client initialization:
        http(s)://centrifuge.example.com
        http(s)://centrifuge.example.com/
        http(s)://centrifuge.example.com/api
        http(s)://centrifuge.example.com/api/
        """
        address = self.address.rstrip("/")
        api_path = "/api"
        if not address.endswith(api_path):
            address += api_path
        return address

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
        url = self.prepare_url()
        data = to_bytes("\n".join([json.dumps(x, cls=self.json_encoder) for x in messages]))
        response = self._send(url, data)
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
            resp = self.session.post(url, data=data, headers=headers, timeout=self.timeout, verify=self.verify)
        except requests.RequestException as err:
            raise RequestException(err)
        if resp.status_code != 200:
            raise RequestException("wrong status code: %d" % resp.status_code)
        return resp.content.decode('utf-8')

    def reset(self):
        self._messages = []

    @staticmethod
    def get_publish_params(channel, data, uid=None):
        params = {
            "channel": channel,
            "data": data
        }
        if uid:
            params['uid'] = uid
        return params

    @staticmethod
    def get_broadcast_params(channels, data, uid=None):
        params = {
            "channels": channels,
            "data": data
        }
        if uid:
            params['uid'] = uid
        return params

    @staticmethod
    def get_unsubscribe_params(user, channel=None):
        params = {"user": user}
        if channel:
            params["channel"] = channel
        return params

    @staticmethod
    def get_disconnect_params(user):
        return {
            "user": user
        }

    @staticmethod
    def get_presence_params(channel):
        return {
            "channel": channel
        }

    @staticmethod
    def get_history_params(channel):
        return {
            "channel": channel
        }

    @staticmethod
    def get_channels_params():
        return {}

    @staticmethod
    def get_info_params():
        return {}

    def _check_empty(self):
        if self._messages:
            raise ClientNotEmpty("client command buffer not empty, send commands or reset client")

    def _send_one(self):
        res = self.send()
        data = res[0]
        if "error" in data and data["error"]:
            raise ResponseError(data["error"])
        return data.get("result")

    def publish(self, channel, data, uid=None):
        self._check_empty()
        self.add("publish", self.get_publish_params(channel, data, uid=uid))
        self._send_one()
        return

    def broadcast(self, channels, data, uid=None):
        self._check_empty()
        self.add("broadcast", self.get_broadcast_params(channels, data, uid=uid))
        self._send_one()
        return

    def unsubscribe(self, user, channel=None):
        self._check_empty()
        self.add("unsubscribe", self.get_unsubscribe_params(user, channel=channel))
        self._send_one()
        return

    def disconnect(self, user):
        self._check_empty()
        self.add("disconnect", self.get_disconnect_params(user))
        self._send_one()
        return

    def presence(self, channel):
        self._check_empty()
        self.add("presence", self.get_presence_params(channel))
        result = self._send_one()
        return result["presence"]

    def history(self, channel):
        self._check_empty()
        self.add("history", self.get_history_params(channel))
        result = self._send_one()
        return result["history"]

    def channels(self):
        self._check_empty()
        self.add("channels", self.get_channels_params())
        result = self._send_one()
        return result["channels"]

    def info(self):
        self._check_empty()
        self.add("info", self.get_info_params())
        result = self._send_one()
        return result
