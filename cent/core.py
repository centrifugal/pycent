# coding: utf-8
#
# Copyright 2013 Alexandr Emelin
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
try:
    from urllib.request import urlopen, Request
except ImportError:
    from urllib2 import urlopen, Request

try:
    import urllib.parse as urlparse
except ImportError:
    import urlparse

import six
import hmac
import json
import base64


AUTH_HEADER_NAME = 'X-Centrifuge-Auth'


class Client(object):

    def __init__(self, address, project_id, secret_key,
                 timeout=2, send_func=None):
        self.address = address
        self.project_id = project_id
        self.secret_key = secret_key
        self.timeout = timeout
        self.send_func = send_func

    def prepare_url(self):
        return '/'.join([self.address.rstrip('/'), self.project_id])

    def sign_encoded_data(self, encoded_data):
        sign = hmac.new(six.b(str(self.secret_key)))
        sign.update(six.b(self.project_id))
        sign.update(encoded_data)
        return sign.hexdigest()

    def create_auth_header_value(self, encoded_data):
        params = {
            "sign": self.sign_encoded_data(encoded_data)
        }
        return " ".join(
            ["%s=%s" % (key, value) for key, value in params.items()]
        )

    def prepare_headers(self, encoded_data):
        auth_header_value = self.create_auth_header_value(encoded_data)
        return {
            AUTH_HEADER_NAME: auth_header_value
        }

    def encode_data(self, data):
        json_data = json.dumps(data)
        base64_data = base64.b64encode(six.b(json_data))
        return base64_data

    def prepare(self, data):
        url = self.prepare_url()
        encoded_data = self.encode_data(data)
        headers = self.prepare_headers(encoded_data)
        return url, headers, encoded_data

    def send(self, method, params):
        data = {
            "method": method,
            "params": params
        }
        if self.send_func:
            return self.send_func(*self.prepare(data))
        return self._send(*self.prepare(data))

    def _send(self, url, headers, encoded_data):
        """
        Send a request to a remote web server using HTTP POST.
        """
        req = Request(url, headers=headers)
        try:
            response = urlopen(req, encoded_data, timeout=self.timeout)
        except Exception as e:
            return None, e
        else:
            data = response.read()
            result = json.loads(data.decode('utf-8'))
            return result, None