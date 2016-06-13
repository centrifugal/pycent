# coding: utf-8
try:
    import urllib.parse as urlparse
except ImportError:
    import urlparse

import sys
import hmac
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


def generate_token(secret, user, timestamp, info=""):
    """
    When client from browser wants to connect to Centrifuge he must send his
    user ID, timestamp and optional info. To validate that data we use HMAC
    SHA-256 to build token.
    @param secret: Centrifugo secret key
    @param user: user ID from your application
    @param timestamp: current timestamp seconds as string
    @param info: optional json encoded data for this client connection
    """
    sign = hmac.new(to_bytes(str(secret)), digestmod=sha256)
    sign.update(to_bytes(user))
    sign.update(to_bytes(timestamp))
    sign.update(to_bytes(info))
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


def generate_api_sign(secret, encoded_data):
    """
    Generate HMAC SHA-256 sign for API request.
    @param secret: Centrifugo secret key
    @param encoded_data: json encoded data to send
    """
    sign = hmac.new(to_bytes(str(secret)), digestmod=sha256)
    sign.update(encoded_data)
    return sign.hexdigest()


class Client(object):

    def __init__(self, address, secret, timeout=1, send_func=None, json_encoder=None, insecure_api=False, **kwargs):
        self.address = address
        self.secret = secret
        self.timeout = timeout
        self.send_func = send_func
        self.json_encoder = json_encoder
        self.insecure_api = insecure_api
        self.kwargs = kwargs
        self._messages = []

    def prepare_url(self):
        """
        http(s)://centrifuge.example.com/api/
        """
        address = self.address.rstrip('/')
        api_path = "/api/"
        if not address.endswith(api_path):
            address += api_path
        return address

    def sign_encoded_data(self, encoded_data):
        return generate_api_sign(self.secret, encoded_data)

    def prepare(self, data):
        url = self.prepare_url()
        encoded_data = to_bytes(json.dumps(data, cls=self.json_encoder))
        if not self.insecure_api:
            sign = self.sign_encoded_data(encoded_data)
        else:
            # no need to generate sign in case of insecure API option on
            sign = ""
        return url, sign, encoded_data

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
        if self.send_func:
            return self.send_func(*self.prepare(messages))
        return self._send(*self.prepare(messages))

    def _send(self, url, sign, encoded_data):
        """
        Send a request to a remote web server using HTTP POST.
        """
        headers = {'Content-type': 'application/json', 'X-API-Sign': sign}
        try:
            resp = requests.post(url, data=encoded_data, headers=headers, timeout=self.timeout)
        except requests.RequestException as err:
            raise RequestException(err)
        return json.loads(resp.content.decode('utf-8'))

    def reset(self):
        self._messages = []

    @staticmethod
    def get_publish_params(channel, data, client=None):
        params = {
            "channel": channel,
            "data": data
        }
        if client:
            params['client'] = client
        return params

    @staticmethod
    def get_broadcast_params(channels, data, client=None):
        params = {
            "channels": channels,
            "data": data
        }
        if client:
            params['client'] = client
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
    def get_stats_params():
        return {}

    def _check_empty(self):
        if self._messages:
            raise ClientNotEmpty("client command buffer not empty, send commands or reset client")

    def _send_one(self):
        res = self.send()
        data = res[0]
        if "error" in data and data["error"]:
            raise ResponseError(data["error"])
        return data.get("body")

    def publish(self, channel, data, client=None):
        self._check_empty()
        self.add("publish", self.get_publish_params(channel, data, client=client))
        self._send_one()
        return

    def broadcast(self, channels, data, client=None):
        self._check_empty()
        self.add("broadcast", self.get_broadcast_params(channels, data, client=client))
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
        body = self._send_one()
        return body["data"]

    def history(self, channel):
        self._check_empty()
        self.add("history", self.get_history_params(channel))
        body = self._send_one()
        return body["data"]

    def channels(self):
        self._check_empty()
        self.add("channels", self.get_channels_params())
        body = self._send_one()
        return body["data"]

    def stats(self):
        self._check_empty()
        self.add("stats", self.get_stats_params())
        body = self._send_one()
        return body["data"]
