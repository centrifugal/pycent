#!/usr/bin/python3

from core import Client
from urllib3 import HTTPConnectionPool


url = "http://localhost:8000"
secret_key = "68ccb437-e54b-421a-b536-ddecd6886fd5"

client = Client(url, secret_key)

channel = "public:chat"
data = {"input": "test"}
client.publish(channel, data)

client.unsubscribe("USER_ID")
client.disconnect("USER_ID")
messages = client.history("public:chat")
clients = client.presence("public:chat")
channels = client.channels()
stats = client.stats()
