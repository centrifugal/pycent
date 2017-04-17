#!/usr/bin/python3

from core import Client
from urllib3 import HTTPConnectionPool


url_requests = "http://localhost:8000"
url_connpool = "localhost:8000"
secret_key = ""

pool = HTTPConnectionPool(url_connpool, maxsize=5)

# client = Client(url_requests, secret_key)
client = Client(url_connpool, secret_key, pool=pool)

channel = "public:chat"
data = {"input": "test"}
client.publish(channel, data)

client.unsubscribe("USER_ID")
client.disconnect("USER_ID")
messages = client.history("public:chat")
clients = client.presence("public:chat")
channels = client.channels()
stats = client.stats()