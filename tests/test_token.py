"""Tokens, JWKS, API tokens and shared poll signatures."""

from __future__ import annotations

import base64
import json
import threading
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, padding, rsa, utils

import cent
from cent import sharedpoll, token

IAT = datetime.fromtimestamp(1700000000, UTC)
EXP = datetime.fromtimestamp(1700003600, UTC)
HMAC = token.Key.hmac(b"client_secret")


def parts(tok: str) -> tuple[dict[str, Any], dict[str, Any], bytes, str]:
    h, p, s = tok.split(".")

    def dec(x: str) -> bytes:
        return base64.urlsafe_b64decode(x + "=" * (-len(x) % 4))

    return json.loads(dec(h)), json.loads(dec(p)), dec(p), s


# The spec's vectors (spec.md, section 15.1).


def test_spec_token_vectors() -> None:
    conn = token.connection(HMAC, token.ConnectionClaims(user="42", expires_at=EXP, issued_at=IAT))
    assert conn == (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiI0MiIsImV4cCI6MTcwMDAwMzYwMCwiaWF0IjoxNzAwMDAwMDAwfQ."
        "HKZwmcYmHVbRESuYd4swVgAH7gg41giR57F_K5FEmEY"
    )
    sub = token.subscription(HMAC, token.SubscriptionClaims(user="42", channel="news", expires_at=EXP, issued_at=IAT))
    assert sub == (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiI0MiIsImV4cCI6MTcwMDAwMzYwMCwiaWF0IjoxNzAwMDAwMDAwLCJjaGFubmVsIjoibmV3cyJ9."
        "v_Quw-azNV1qFjm9ZQnkp6QBtK6LmtFxY74YcUHlJcA"
    )


def test_spec_shared_poll_vectors() -> None:
    assert sharedpoll._sign_at("shared_poll_secret", "42", "poll:prices", ["AAPL", "GOOG"], EXP, now=1700000000) == (
        "1700000000:1700003600:c61dbf52085a6973537e71644fa30a3bbfc29a52d7ce9f1b7618531596ce587d"
    )
    assert sharedpoll._sign_at("shared_poll_secret", "", "poll:prices", [], token.NEVER, now=1700000000) == (
        "1700000000:0:92dd64af5612afde06cad03bb63435d951e037cb55a087af05c2a1399abade0e"
    )


def test_shared_poll_sign() -> None:
    sig = sharedpoll.sign(
        b"s", user="u", channel="poll:x", keys=["a"], expires_at=datetime.now(UTC) + timedelta(minutes=1)
    )
    iat, exp, mac = sig.split(":")
    assert int(exp) - int(iat) in (59, 60)
    assert len(mac) == 64
    # A colon cannot move between user and channel.
    assert sharedpoll._sign_at("s", "alice", "news:tech", [], token.NEVER, now=1) != sharedpoll._sign_at(
        "s", "alice:news", "tech", [], token.NEVER, now=1
    )
    with pytest.raises(ValueError, match="naive"):
        sharedpoll.sign("s", user="u", channel="c", keys=[], expires_at=datetime(2030, 1, 1))
    with pytest.raises(cent.InvalidRequestError, match="empty secret"):
        sharedpoll.sign("", user="u", channel="c", keys=[], expires_at=token.NEVER)
    # The expiry is chosen explicitly: never is spelled, a number or a duration refused.
    assert sharedpoll.sign("s", user="u", channel="c", keys=[], expires_at=token.NEVER).split(":")[1] == "0"
    with pytest.raises(TypeError, match="missing 1 required keyword-only argument: 'expires_at'"):
        sharedpoll.sign("s", user="u", channel="c", keys=[])  # type: ignore[call-arg]
    for bad in (None, 1700000000, timedelta(hours=1)):
        with pytest.raises(TypeError, match=r"token\.NEVER"):
            sharedpoll.sign("s", user="u", channel="c", keys=[], expires_at=bad)  # type: ignore[arg-type]


# Claims.


def test_connection_claims_on_the_wire() -> None:
    tok = token.connection(
        HMAC,
        token.ConnectionClaims(
            user="42",
            expires_at=EXP,
            connection_expires_at=token.NEVER,
            issued_at=IAT,
            id="t1",
            audience="aud",
            issuer="iss",
            info={"name": "Alice"},
            subs={
                "news": token.SubscribeOptions(
                    data=cent.RawJSON('{"n": 1.0}'),
                    override=cent.SubscribeOptionOverride(presence=True),
                )
            },
            meta={"plan": "pro"},
            caps=[token.ChannelsCapability(channels=["chat:*"], allow=["sub"], match="wildcard")],
            labels={"region": "eu"},
        ),
    )
    header, claims, raw, _ = parts(tok)
    assert header == {"alg": "HS256", "typ": "JWT"}
    assert raw == (
        b'{"sub":"42","exp":1700003600,"iat":1700000000,"jti":"t1","aud":"aud","iss":"iss","expire_at":0,'
        b'"info":{"name":"Alice"},"subs":{"news":{"data":{"n": 1.0},"override":{"presence":{"value":true}}}},'
        b'"meta":{"plan":"pro"},"caps":[{"channels":["chat:*"],"allow":["sub"],"match":"wildcard"}],'
        b'"labels":{"region":"eu"}}'
    )
    assert claims["sub"] == "42"


def test_expiry() -> None:
    _, c, _, _ = parts(token.connection(HMAC, token.ConnectionClaims(user="u", expires_at=token.NEVER)))
    assert "exp" not in c
    assert "expire_at" not in c
    _, c, _, _ = parts(
        token.subscription(
            HMAC, token.SubscriptionClaims(channel="ch", expires_at=EXP, subscription_expires_at=IAT + timedelta(1))
        )
    )
    assert c["exp"] == 1700003600
    assert c["expire_at"] == 1700000000 + 86400
    # Time zones are honoured.
    tz = timezone(timedelta(hours=3))
    _, c, _, _ = parts(token.connection(HMAC, token.ConnectionClaims(expires_at=EXP.astimezone(tz))))
    assert c["exp"] == 1700003600


def test_claims_refused() -> None:
    with pytest.raises(TypeError):
        token.ConnectionClaims(user="u")  # type: ignore[call-arg]
    with pytest.raises(ValueError, match="naive"):
        token.connection(HMAC, token.ConnectionClaims(expires_at=datetime(2030, 1, 1)))
    with pytest.raises(ValueError, match="channels or subs"):
        token.connection(
            HMAC, token.ConnectionClaims(expires_at=EXP, channels=["a"], subs={"b": token.SubscribeOptions()})
        )
    with pytest.raises(ValueError, match="needs a channel"):
        token.subscription(HMAC, token.SubscriptionClaims(channel="", expires_at=EXP))
    with pytest.raises(cent.InvalidRequestError, match="info"):
        token.connection(HMAC, token.ConnectionClaims(expires_at=EXP, info={"x": float("nan")}))
    with pytest.raises(ValueError, match="empty HMAC secret"):
        token.Key.hmac(b"")
    with pytest.raises(ValueError, match="required"):
        token.connection(HMAC, token.ConnectionClaims(expires_at=None))  # type: ignore[arg-type]


# Asymmetric keys, verified against their public keys.


def _verify(tok: str, pub: Any, alg: str) -> None:
    h, p, s = tok.split(".")
    signed = (h + "." + p).encode()
    sig = base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))
    if alg == "RS256":
        pub.verify(sig, signed, padding.PKCS1v15(), hashes.SHA256())
    elif alg == "EdDSA":
        pub.verify(sig, signed)
    else:
        size = len(sig) // 2
        r, ss = int.from_bytes(sig[:size], "big"), int.from_bytes(sig[size:], "big")
        h_alg = {"ES256": hashes.SHA256(), "ES384": hashes.SHA384(), "ES512": hashes.SHA512()}[alg]
        pub.verify(utils.encode_dss_signature(r, ss), signed, ec.ECDSA(h_alg))


@pytest.mark.parametrize(
    ("make", "alg", "size"),
    [
        (lambda: rsa.generate_private_key(public_exponent=65537, key_size=2048), "RS256", 256),
        (lambda: ec.generate_private_key(ec.SECP256R1()), "ES256", 64),
        (lambda: ec.generate_private_key(ec.SECP384R1()), "ES384", 96),
        (lambda: ec.generate_private_key(ec.SECP521R1()), "ES512", 132),
        (ed25519.Ed25519PrivateKey.generate, "EdDSA", 64),
    ],
)
def test_asymmetric_keys(make: Any, alg: str, size: int) -> None:
    priv = make()
    pem = priv.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    own: Any = {"RS256": token.Key.rsa, "EdDSA": token.Key.ed25519}.get(alg, token.Key.ecdsa)
    for key in (own(priv), token.Key.from_pem(pem)):
        k = key.with_key_id("k1")
        tok = token.connection(k, token.ConnectionClaims(user="u", expires_at=EXP))
        header, _, _, s = parts(tok)
        assert header == {"alg": alg, "typ": "JWT", "kid": "k1"}
        assert len(base64.urlsafe_b64decode(s + "==")) == size
        _verify(tok, priv.public_key(), alg)


def test_unsupported_curve() -> None:
    with pytest.raises(ValueError, match="P-256, P-384 or P-521"):
        token.Key.ecdsa(ec.generate_private_key(ec.SECP256K1()))


# JWKS.


def test_jwks() -> None:
    r = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    e = ec.generate_private_key(ec.SECP384R1())
    o = ed25519.Ed25519PrivateKey.generate()
    set_ = json.loads(
        token.jwks(
            token.Key.rsa(r).with_key_id("r"),
            token.Key.ecdsa(e).with_key_id("e"),
            token.Key.ed25519(o).with_key_id("o"),
        )
    )
    rk, ek, ok = set_["keys"]
    assert (rk["kty"], rk["use"], rk["alg"], rk["kid"]) == ("RSA", "sig", "RS256", "r")
    n = int.from_bytes(base64.urlsafe_b64decode(rk["n"] + "=="), "big")
    assert n == r.public_key().public_numbers().n
    assert (ek["crv"], ek["alg"]) == ("P-384", "ES384")
    assert len(base64.urlsafe_b64decode(ek["x"] + "==")) == 48
    assert ok == {
        "kty": "OKP",
        "kid": "o",
        "use": "sig",
        "alg": "EdDSA",
        "crv": "Ed25519",
        "x": base64.urlsafe_b64encode(
            o.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        )
        .rstrip(b"=")
        .decode(),
    }


def test_jwks_refused() -> None:
    k = token.Key.ed25519(ed25519.Ed25519PrivateKey.generate())
    with pytest.raises(ValueError, match="without keys"):
        token.jwks()
    with pytest.raises(ValueError, match="HMAC"):
        token.jwks(HMAC.with_key_id("h"))
    with pytest.raises(ValueError, match="no key ID"):
        token.jwks(k)
    with pytest.raises(ValueError, match="used twice"):
        token.jwks(k.with_key_id("a"), k.with_key_id("a"))


# Server API tokens.


def _ed() -> token.Key:
    return token.Key.ed25519(ed25519.Ed25519PrivateKey.generate()).with_key_id("api-1")


def test_api_token() -> None:
    tok = token.api(
        _ed(),
        token.APIClaims(
            audience="centrifugo-api",
            scope=["centrifugo:api", "other"],
            issuer="app",
            subject="billing",
            expires_at=datetime.fromtimestamp(1700000300, UTC),
            issued_at=IAT,
            id="t1",
        ),
    )
    header, _, raw, _ = parts(tok)
    assert header == {"alg": "EdDSA", "typ": "JWT", "kid": "api-1"}
    assert raw == (
        b'{"sub":"billing","exp":1700000300,"iat":1700000000,"jti":"t1","aud":"centrifugo-api","iss":"app",'
        b'"scope":"centrifugo:api other"}'
    )


@pytest.mark.parametrize(
    ("key", "claims", "msg"),
    [
        (HMAC.with_key_id("h"), {"audience": "a", "expires_at": EXP}, "RSA, ECDSA or Ed25519"),
        (token.Key.ed25519(ed25519.Ed25519PrivateKey.generate()), {"audience": "a", "expires_at": EXP}, "key ID"),
        (None, {"issuer": "app", "expires_at": EXP}, "audience or scope"),
        (None, {"audience": "a"}, "expires_at"),
        (None, {"scope": [""], "expires_at": EXP}, "empty or has a space"),
        (None, {"scope": ["a b"], "expires_at": EXP}, "empty or has a space"),
    ],
)
def test_api_token_refused(key: token.Key | None, claims: dict[str, Any], msg: str) -> None:
    with pytest.raises(ValueError, match=msg):
        token.api(key or _ed(), token.APIClaims(**claims))


def test_api_tokens_reused_for_half_the_ttl() -> None:
    keys = [_ed(), token.Key.ed25519(ed25519.Ed25519PrivateKey.generate()).with_key_id("api-2")]
    current = [0]
    tokens = token.APITokens(claims=token.APIClaims(audience="aud"), current_key=lambda: keys[current[0]], ttl=3600)
    first = tokens.token()
    _, c, _, _ = parts(first)
    assert c["exp"] - c["iat"] == 3600
    current[0] = 1
    assert tokens.token() == first
    tokens._refresh_at = 0  # half the ttl passed
    nxt = tokens.token()
    assert parts(nxt)[0]["kid"] == "api-2"

    got: list[str] = []
    threads = [threading.Thread(target=lambda: got.append(tokens.token())) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert set(got) == {nxt}


def test_api_tokens_default_ttl_and_refusals() -> None:
    _, c, _, _ = parts(token.APITokens(key=_ed(), claims=token.APIClaims(audience="a")).token())
    assert c["exp"] - c["iat"] == 300
    with pytest.raises(ValueError, match="sets expires_at"):
        token.APITokens(key=_ed(), claims=token.APIClaims(audience="a", expires_at=EXP))
    with pytest.raises(ValueError, match="positive"):
        token.APITokens(key=_ed(), claims=token.APIClaims(audience="a"), ttl=-1)
    with pytest.raises(ValueError, match="one of them"):
        token.APITokens(claims=token.APIClaims(audience="a"))
    with pytest.raises(ValueError, match="audience or scope"):
        token.APITokens(key=_ed(), claims=token.APIClaims()).token()
