0.4.0
=====

Cent 0.4.0 reflects Centrifuge 0.8.0 changes. Centrifuge 0.8.0 uses project name as API key instead of project ID

How to migrate
==============

* use project key (project name) instead of project ID when creating `Client` instance
* use `key` instead of `project_id` in console tool configuration file
* use `secret` instead of `secret_key` in console tool configuration file

So instead of that:
```
[football]
address = http://localhost:8000/api
project_id = 51b229f778b83c2eced3a76b
secret_key = 994021f2dc354d7893d88b90d430498e
timeout = 5
```

Write this:
```
[football]
address = http://localhost:8000/api
key = football
secret = 994021f2dc354d7893d88b90d430498e
timeout = 5
```


0.3.0
=====

works with Centrifuge >= 0.7.0

* `user_info` kwarg renamed to `info` in `generate_token` method
* new `generate_channel_sign` method to generate auth sign for private channel subscriptions
* use `sha256` hashing algorithm to generate HMACs

0.2.1
=====

* Added `json_encoder` keyword argument to use custom JsonEncoder