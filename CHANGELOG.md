0.3.0
=====

works with Centrifuge >= 0.7.0

* `user_info` kwarg renamed to `info` in `generate_token` method
* new `generate_channel_auth` method to generate auth sign for private channel subscriptions
* use `sha256` hashing algorithm to generate HMACs

0.2.1
=====

* Added `json_encoder` keyword argument to use custom JsonEncoder