# coding: utf-8
try:
    from urllib.request import urlopen, Request
except ImportError:
    from urllib2 import urlopen, Request

try:
    from urllib import urlencode
except ImportError:
    # python 3
    # noinspection PyUnresolvedReferences
    from urllib.parse import urlencode

try:
    import urllib.parse as urlparse
except ImportError:
    import urlparse

import six
import hmac
import json
from hashlib import sha256


class CentException(Exception):
    pass


class ClientNotEmpty(CentException):
    pass


class MalformedResponse(CentException):
    pass


class ResponseError(CentException):
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
    sign = hmac.new(six.b(str(secret)), digestmod=sha256)
    sign.update(six.b(user))
    sign.update(six.b(timestamp))
    sign.update(six.b(info))
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
    auth = hmac.new(six.b(str(secret)), digestmod=sha256)
    auth.update(six.b(str(client)))
    auth.update(six.b(str(channel)))
    auth.update(six.b(info))
    return auth.hexdigest()


def generate_api_sign(secret, encoded_data):
    """
    Generate HMAC SHA-256 sign for API request.
    @param secret: Centrifugo secret key
    @param encoded_data: json encoded data to send
    """
    sign = hmac.new(six.b(str(secret)), digestmod=sha256)
    sign.update(encoded_data)
    return sign.hexdigest()


class Client(object):

    def __init__(self, address, secret, timeout=2, send_func=None, json_encoder=None, insecure_api=False, **kwargs):
        self.address = address
        self.secret = secret
        self.timeout = timeout
        self.send_func = send_func
        self.json_encoder = json_encoder
        self.insecure_api = insecure_api
        self.kwargs = kwargs
        self.messages = []

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
        encoded_data = six.b(json.dumps(data, cls=self.json_encoder))
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
        self.messages.append(data)

    def send(self, method=None, params=None):
        if method and params is not None:
            self.add(method, params)
        messages = self.messages[:]
        self.messages = []
        if self.send_func:
            return self.send_func(*self.prepare(messages))
        return self._send(*self.prepare(messages))

    def _send(self, url, sign, encoded_data):
        """
        Send a request to a remote web server using HTTP POST.
        """
        req = Request(url)
        try:
            response = urlopen(
                req,
                six.b(urlencode({'sign': sign, 'data': encoded_data})),
                timeout=self.timeout
            )
        except Exception as e:
            return None, e
        else:
            data = response.read()
            result = json.loads(data.decode('utf-8'))
            return result, None

    def reset(self):
        self.messages = []

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
        if self.messages:
            raise ClientNotEmpty("client messages not empty, send commands or reset client")

    def _send_one(self):
        res, err = self.send()
        if err:
            return None, err
        if not res:
            return None, MalformedResponse("empty response")
        data = res[0]
        if "error" in data and data["error"]:
            return None, ResponseError(data["error"])
        if "body" not in data:
            return None, MalformedResponse("response body not found")
        return data["body"], None

    def publish(self, channel, data, client=None):
        self._check_empty()
        self.add("publish", self.get_publish_params(channel, data, client=client))
        _, error = self._send_one()
        return error

    def broadcast(self, channels, data, client=None):
        self._check_empty()
        self.add("broadcast", self.get_broadcast_params(channels, data, client=client))
        _, error = self._send_one()
        return error

    def unsubscribe(self, user, channel=None):
        self._check_empty()
        self.add("unsubscribe", self.get_unsubscribe_params(user, channel=channel))
        _, error = self._send_one()
        return error

    def disconnect(self, user):
        self._check_empty()
        self.add("disconnect", self.get_disconnect_params(user))
        _, error = self._send_one()
        return error

    def presence(self, channel):
        self._check_empty()
        self.add("presence", self.get_presence_params(channel))
        body, error = self._send_one()
        if not error:
            if "data" not in body:
                return None, ResponseError("presence data not found in response body")
            return body["data"], None
        return None, error

    def history(self, channel):
        self._check_empty()
        self.add("history", self.get_history_params(channel))
        body, error = self._send_one()
        if not error:
            if "data" not in body:
                return None, ResponseError("history data not found in response body")
            return body["data"], None
        return None, error

    def channels(self):
        self._check_empty()
        self.add("channels", self.get_channels_params())
        body, error = self._send_one()
        if not error:
            if "data" not in body:
                return None, ResponseError("channels data not found in response body")
            return body["data"], None
        return None, error

    def stats(self):
        self._check_empty()
        self.add("stats", self.get_stats_params())
        body, error = self._send_one()
        if not error:
            if "data" not in body:
                return None, ResponseError("stats data not found in response body")
            return body["data"], None
        return None, error
