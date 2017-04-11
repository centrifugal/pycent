#!/usr/bin/python3

from core import Client
# from cent import Client
from urllib3 import HTTPConnectionPool


# url = "http://localhost:8000"
url = "localhost:8000"
secret_key = "9a55d4e8-1539-4560-96e8-5fa6ed31fdf5"

pool = HTTPConnectionPool(url, maxsize=5)

# client = Client(url, secret_key)
client = Client(url, secret_key, pool=pool)

channel = "public:chat"
data = {"input": "test"}
client.publish(channel, data)

client.unsubscribe("USER_ID")
client.disconnect("USER_ID")
messages = client.history("public:chat")
clients = client.presence("public:chat")
channels = client.channels()
stats = client.stats()
