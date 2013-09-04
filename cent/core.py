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
import base64


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

    def encode_data(self, data):
        json_data = json.dumps(data)
        base64_data = base64.b64encode(six.b(json_data))
        return base64_data

    def get_sign(self, encoded_data):
        return self.sign_encoded_data(encoded_data)

    def prepare(self, data):
        url = self.prepare_url()
        encoded_data = self.encode_data(data)
        sign = self.get_sign(encoded_data)
        return url, sign, encoded_data

    def send(self, method, params):
        data = {
            "method": method,
            "params": params
        }
        if self.send_func:
            return self.send_func(*self.prepare(data))
        return self._send(*self.prepare(data))

    def _send(self, url, sign, encoded_data):
        """
        Send a request to a remote web server using HTTP POST.
        """
        req = Request(url)
        try:
            response = urlopen(
                req,
                urlencode({'sign': sign, 'data': encoded_data}),
                timeout=self.timeout
            )
        except Exception as e:
            return None, e
        else:
            data = response.read()
            result = json.loads(data.decode('utf-8'))
            return result, None