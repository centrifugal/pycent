#!/usr/bin/env python
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
from __future__ import print_function
import argparse
import os
import sys
import json

try:
    import configparser as ConfigParser
except ImportError:
    import ConfigParser

from .core import Client


def run():

    parser = argparse.ArgumentParser(description='Centrifuge client')

    parser.add_argument(
        'section', metavar='SECTION', type=str, help='section key from cent configuration file'
    )
    parser.add_argument(
        'method', metavar='METHOD', type=str, help='call method'
    )
    parser.add_argument(
        '--params', type=str, help='params data', default='{}'
    )
    parser.add_argument(
        '--config', type=str, default="~/.centrc", help='cent configuration file'
    )

    options = parser.parse_args()

    config_file = os.path.expanduser(options.config)
    config = ConfigParser.ConfigParser()
    config.read(config_file)

    if not options.section in config.sections():
        print(
            "Section {0} not found in {1} configuration file".format(
                options.section, options.config
            )
        )
        sys.exit(1)

    try:
        address = config.get(options.section, 'address')
        project_id = config.get(options.section, 'project_id')
        secret_key = config.get(options.section, 'secret_key')
        try:
            timeout = config.getint(options.section, 'timeout')
        except:
            timeout = 2
    except Exception as e:
        print(e)
        sys.exit(1)

    if not sys.stdin.isatty():
        json_data = sys.stdin.read().strip()
    else:
        json_data = options.params

    try:
        params = json.loads(json_data)
    except Exception as e:
        print(e)
        sys.exit(1)

    if not params:
        print("no params, nothing to do")
        sys.exit(1)

    client = Client(
        address,
        project_id,
        secret_key,
        timeout=timeout
    )

    if not isinstance(params, dict):
        print("params must be valid JSON object")
        sys.exit(1)

    response = client.send(options.method, params)
    result, error = response
    if error:
        print(error)
        sys.exit(1)
    else:
        print(result)


if __name__ == '__main__':
    run()