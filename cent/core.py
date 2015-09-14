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


class ClientNotEmpty(Exception):
    pass


class MalformedResponse(Exception):
    pass


def generate_token(project_secret, project_key, user, timestamp, info=""):
    """
    When client from browser wants to connect to Centrifuge he must send his
    user ID, project key, timestamp and optional info. To validate that data 
    we use HMAC to build token.
    """
    sign = hmac.new(six.b(str(project_secret)), digestmod=sha256)
    sign.update(six.b(project_key))
    sign.update(six.b(user))
    sign.update(six.b(timestamp))
    sign.update(six.b(info))
    token = sign.hexdigest()
    return token


def generate_channel_sign(project_secret, client, channel, info=""):
    """
    Generate HMAC sign for private channel subscription
    """
    auth = hmac.new(six.b(str(project_secret)), digestmod=sha256)
    auth.update(six.b(str(client)))
    auth.update(six.b(str(channel)))
    auth.update(six.b(info))
    return auth.hexdigest()


def generate_api_sign(project_secret, project_key, encoded_data):
    """
    Generate HMAC sign for api request
    """
    sign = hmac.new(six.b(str(project_secret)), digestmod=sha256)
    sign.update(six.b(project_key))
    sign.update(encoded_data)
    return sign.hexdigest()


class Client(object):

    def __init__(self, address, project_key, project_secret, timeout=2, send_func=None, json_encoder=None, **kwargs):
        self.address = address
        self.key = project_key
        self.secret = project_secret
        self.timeout = timeout
        self.send_func = send_func
        self.json_encoder = json_encoder
        self.kwargs = kwargs
        self.messages = []

    def prepare_url(self):
        """
        http(s)://centrifuge.example.com/api/PROJECT_KEY
        """
        address = self.address.rstrip('/')
        api_path = "/api"
        if not address.endswith(api_path):
            address += api_path
        return '/'.join([address, self.key])

    def sign_encoded_data(self, encoded_data):
        return generate_api_sign(self.secret, self.key, encoded_data)

    def prepare(self, data):
        url = self.prepare_url()
        encoded_data = six.b(json.dumps(data, cls=self.json_encoder))
        sign = self.sign_encoded_data(encoded_data)
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

    def _check_empty(self):
        if self.messages:
            raise ClientNotEmpty("client messages not empty, send commands or reset client")

    def _send_one(self):
        res, err = self.send()
        if err:
            return None, err
        if not res:
            return None, MalformedResponse("empty response")
        return res[0], None

    def publish(self, channel, data, client=None):
        self._check_empty()
        self.add("publish", self.get_publish_params(channel, data, client=client))
        return self._send_one()

    def unsubscribe(self, user, channel=None):
        self._check_empty()
        self.add("unsubscribe", self.get_unsubscribe_params(user, channel=channel))
        return self._send_one()

    def disconnect(self, user):
        self._check_empty()
        self.add("disconnect", self.get_disconnect_params(user))
        return self._send_one()

    def presence(self, channel):
        self._check_empty()
        self.add("presence", self.get_presence_params(channel))
        return self._send_one()

    def history(self, channel):
        self._check_empty()
        self.add("history", self.get_history_params(channel))
        return self._send_one()

    def channels(self):
        self._check_empty()
        self.add("channels", self.get_channels_params())
        return self._send_one()
