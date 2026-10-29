"""Tokens: connection and subscription tokens for client SDKs, the JSON Web Key
Set Centrifugo verifies them with, and Centrifugo PRO's server API tokens.

>>> from cent import token
>>> key = token.Key.hmac(b"secret")       # client.token.hmac_secret_key
>>> token.connection(key, token.ConnectionClaims(
...     user="42", expires_at=datetime.now(UTC) + timedelta(minutes=15)))

See https://centrifugal.dev/docs/server/authentication. HMAC keys need
nothing but the standard library; RSA, ECDSA and Ed25519 keys need the
cryptography package: ``pip install cent[crypto]``.
"""

from __future__ import annotations

import base64
import hashlib
import hmac as _hmac
import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Final

from cent import _wire as _w
from cent._api import FilterNode, SubscribeOptionOverride
from cent._errors import InvalidRequestError
from cent._payload import JSON

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa

__all__ = [
    "NEVER",
    "APIClaims",
    "APITokens",
    "ChannelsCapability",
    "ConnectionClaims",
    "Key",
    "Never",
    "SubscribeOptions",
    "SubscriptionClaims",
    "api",
    "connection",
    "jwks",
    "subscription",
]


class Never:
    """The type of NEVER: an expiry chosen to be never."""

    _instance: Never | None = None

    def __new__(cls) -> Never:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "NEVER"


NEVER: Final = Never()
"""An expiry which never comes: for expires_at, a token accepted forever -
and forever once leaked; for connection_expires_at and
subscription_expires_at, a connection or subscription which never expires.
Always chosen explicitly."""


def _crypto() -> Any:
    try:
        # Imported when needed: cryptography is optional, for HMAC keys need none.
        from cryptography.hazmat.primitives import hashes, serialization  # noqa: PLC0415
        from cryptography.hazmat.primitives.asymmetric import ec, ed25519, padding, rsa, utils  # noqa: PLC0415
    except ImportError as e:  # pragma: no cover - depends on the environment
        raise ImportError("RSA, ECDSA and Ed25519 keys need the cryptography package: pip install cent[crypto]") from e
    return hashes, serialization, ec, ed25519, padding, rsa, utils


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


_EC_ALGS = {
    "secp256r1": ("ES256", "P-256", 32),
    "secp384r1": ("ES384", "P-384", 48),
    "secp521r1": ("ES512", "P-521", 66),
}


class Key:
    """A key signing tokens, matching the one Centrifugo verifies with. Make one
    with Key.hmac, Key.rsa, Key.ecdsa, Key.ed25519 or Key.from_pem."""

    __slots__ = ("_alg", "_jwk", "_kid", "_sign")

    def __init__(self, alg: str, sign: Callable[[bytes], bytes], jwk: dict[str, str] | None, kid: str = "") -> None:
        self._alg = alg
        self._sign = sign
        # The public key as a JSON Web Key, for jwks; None for HMAC.
        self._jwk = jwk
        self._kid = kid

    @property
    def alg(self) -> str:
        """The JWS algorithm: HS256, RS256, ES256, ES384, ES512 or EdDSA."""
        return self._alg

    @property
    def kid(self) -> str:
        """The key ID written as the tokens' "kid", if set."""
        return self._kid

    def with_key_id(self, kid: str) -> Key:
        """The key, with kid as the "kid" of the tokens it signs: the ID of its
        public key in the JWKS Centrifugo verifies with. Never give the ID of
        a key to another: Centrifugo caches keys by ID, and would refuse the
        other key's tokens until its cache expires."""
        if not isinstance(kid, str) or not kid:
            raise InvalidRequestError("token: a key ID must be a non-empty str")
        return Key(self._alg, self._sign, self._jwk, kid)

    def __repr__(self) -> str:
        return f"Key({self._alg}{', kid=' + repr(self._kid) if self._kid else ''})"

    @staticmethod
    def hmac(secret: bytes | str) -> Key:
        """A key signing with HS256 and secret: Centrifugo's
        client.token.hmac_secret_key."""
        s = secret.encode() if isinstance(secret, str) else bytes(secret)
        if not s:
            raise InvalidRequestError("token: empty HMAC secret")
        return Key("HS256", lambda data: _hmac.new(s, data, hashlib.sha256).digest(), None)

    @staticmethod
    def rsa(private_key: rsa.RSAPrivateKey) -> Key:
        """A key signing with RS256, whose public key is Centrifugo's
        client.token.rsa_public_key."""
        hashes, _, _, _, padding, rsa_mod, _ = _crypto()
        if not isinstance(private_key, rsa_mod.RSAPrivateKey):
            raise TypeError("token: Key.rsa takes an RSAPrivateKey")
        pub = private_key.public_key().public_numbers()
        jwk = {
            "kty": "RSA",
            "n": _b64(pub.n.to_bytes((pub.n.bit_length() + 7) // 8, "big")),
            "e": _b64(pub.e.to_bytes((pub.e.bit_length() + 7) // 8, "big")),
        }
        return Key("RS256", lambda data: private_key.sign(data, padding.PKCS1v15(), hashes.SHA256()), jwk)

    @staticmethod
    def ecdsa(private_key: ec.EllipticCurvePrivateKey) -> Key:
        """A key signing with ES256, ES384 or ES512 - for a P-256, P-384 or P-521
        key - whose public key is Centrifugo's client.token.ecdsa_public_key."""
        hashes, _, ec_mod, _, _, _, utils = _crypto()
        if not isinstance(private_key, ec_mod.EllipticCurvePrivateKey):
            raise TypeError("token: Key.ecdsa takes an EllipticCurvePrivateKey")
        curve = private_key.curve.name
        if curve not in _EC_ALGS:
            raise InvalidRequestError(f"token: ECDSA curve {curve}, want P-256, P-384 or P-521")
        alg, crv, size = _EC_ALGS[curve]
        digest = {"ES256": hashes.SHA256, "ES384": hashes.SHA384, "ES512": hashes.SHA512}[alg]()
        pub = private_key.public_key().public_numbers()
        jwk = {"kty": "EC", "crv": crv, "x": _b64(pub.x.to_bytes(size, "big")), "y": _b64(pub.y.to_bytes(size, "big"))}

        def sign(data: bytes) -> bytes:
            # JWS wants r and s as fixed-size big-endian halves, not DER.
            r, s = utils.decode_dss_signature(private_key.sign(data, ec_mod.ECDSA(digest)))
            return bytes(r.to_bytes(size, "big") + s.to_bytes(size, "big"))

        return Key(alg, sign, jwk)

    @staticmethod
    def ed25519(private_key: ed25519.Ed25519PrivateKey) -> Key:
        """A key signing with EdDSA, whose public key is Centrifugo's
        client.token.ed25519_public_key (Centrifugo v6.10.2+), or is published
        in its JWKS with jwks."""
        _, serialization, _, ed_mod, _, _, _ = _crypto()
        if not isinstance(private_key, ed_mod.Ed25519PrivateKey):
            raise TypeError("token: Key.ed25519 takes an Ed25519PrivateKey")
        raw = private_key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        return Key("EdDSA", private_key.sign, {"kty": "OKP", "crv": "Ed25519", "x": _b64(raw)})

    @staticmethod
    def from_pem(pem: bytes | str, password: bytes | None = None) -> Key:
        """The key of a PEM-encoded private key - RSA, ECDSA or Ed25519 - as
        Key.rsa, Key.ecdsa or Key.ed25519 make it."""
        _, serialization, ec_mod, ed_mod, _, rsa_mod, _ = _crypto()
        data = pem.encode() if isinstance(pem, str) else pem
        k = serialization.load_pem_private_key(data, password)
        if isinstance(k, rsa_mod.RSAPrivateKey):
            return Key.rsa(k)
        if isinstance(k, ec_mod.EllipticCurvePrivateKey):
            return Key.ecdsa(k)
        if isinstance(k, ed_mod.Ed25519PrivateKey):
            return Key.ed25519(k)
        raise InvalidRequestError(f"token: unsupported private key type {type(k).__name__}")


def _unix(dt: datetime, name: str) -> int:
    if not isinstance(dt, datetime):
        raise TypeError(f"token: {name} must be a datetime, not {type(dt).__name__}")
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise InvalidRequestError(f"token: {name} is a naive datetime: give it a time zone, datetime.now(UTC) say")
    return int(dt.timestamp())


def _expiry(expires_at: datetime | Never, name: str) -> int | None:
    """The "exp" claim of expires_at: None to leave it out, for NEVER."""
    if expires_at is NEVER:
        return None
    if expires_at is None:
        raise InvalidRequestError(f"token: {name} is required: a datetime, or token.NEVER for a token accepted forever")
    return _unix(expires_at, name)  # type: ignore[arg-type]


def _session_expiry(at: datetime | Never | None, name: str) -> int | None:
    """The "expire_at" claim: left out (None), 0 for never, or a time."""
    if at is None:
        return None
    if at is NEVER:
        return 0
    return _unix(at, name)  # type: ignore[arg-type]


@dataclass(slots=True, kw_only=True)
class ChannelsCapability:
    """Operations granted in channels: a connection may do an operation in a
    channel when any of its capabilities allows the operation and matches the
    channel. Centrifugo PRO only."""

    channels: list[str] = field(default_factory=list)
    """The channels, or channel patterns, it applies to."""

    allow: list[str] = field(default_factory=list)
    """The operations: "sub" (subscribe), "pub" (publish), "hst" (history),
    "prs" (presence)."""

    match: str = ""
    """How channels are matched: empty for exact names, "wildcard" or "regex"."""

    def _to_wire(self) -> dict[str, Any]:
        w: dict[str, Any] = {}
        if self.channels:
            w["channels"] = list(self.channels)
        if self.allow:
            w["allow"] = list(self.allow)
        if self.match:
            w["match"] = self.match
        return w


@dataclass(slots=True, kw_only=True)
class SubscribeOptions:
    """The options of a server-side subscription in ConnectionClaims.subs."""

    info: JSON = None
    """Channel-specific information about the connection."""

    b64info: str = ""
    """Binary info in base64, instead of info."""

    data: JSON = None
    """Sent to the client with the subscription."""

    b64data: str = ""
    """Binary data in base64, instead of data."""

    override: SubscribeOptionOverride | None = None
    """Channel options of the namespace overridden for this subscription."""

    server_tags_filter: FilterNode | None = None
    """Only publications whose tags match it are delivered. Centrifugo PRO
    only, which refuses a malformed filter: the subscription fails."""

    def _to_wire(self) -> dict[str, Any]:
        w: dict[str, Any] = {}
        if self.info is not None:
            w["info"] = _w.payload(self.info, "info")
        if self.b64info:
            w["b64info"] = self.b64info
        if self.data is not None:
            w["data"] = _w.payload(self.data, "data")
        if self.b64data:
            w["b64data"] = self.b64data
        if self.override is not None and (o := self.override._to_wire()):
            w["override"] = o
        if self.server_tags_filter is not None and (f := self.server_tags_filter._to_wire()):
            w["server_tags_filter"] = f
        return w


@dataclass(slots=True, kw_only=True)
class ConnectionClaims:
    """The claims of a connection token. See
    https://centrifugal.dev/docs/server/authentication."""

    user: str = ""
    """The ID of the connection's user: the "sub" claim. Empty for an anonymous
    connection."""

    expires_at: datetime | Never
    """Until when the token is accepted: the "exp" claim, an aware datetime, or
    NEVER for a token accepted forever - and forever once leaked, for a
    trusted service's own connection, say. Required. The connection expires
    then too, unless connection_expires_at says otherwise: Centrifugo asks the
    client for a new token, and closes the connection without one."""

    connection_expires_at: datetime | Never | None = None
    """When set, when the connection expires instead of at expires_at: the
    "expire_at" claim. NEVER makes the connection never expire - Centrifugo
    never asks for a new token - while expires_at still bounds when the token
    is accepted, on reconnects too. Most applications leave it unset."""

    issued_at: datetime | None = None
    """The "iat" claim; None for now."""

    id: str = ""
    """The "jti" claim, for Centrifugo PRO's token revocation."""

    audience: str = ""
    """The "aud" claim: client.token.audience."""

    issuer: str = ""
    """The "iss" claim: client.token.issuer."""

    info: JSON = None
    """Information about the connection: in presence, join and leave events,
    and the client's publications."""

    b64info: str = ""
    """Binary info in base64, instead of info."""

    channels: list[str] = field(default_factory=list)
    """Server-side channels to subscribe the connection to."""

    subs: dict[str, SubscribeOptions] = field(default_factory=dict)
    """Server-side channels to subscribe the connection to, each with its
    options. Set channels or subs, not both: Centrifugo ignores channels when
    subs is set."""

    meta: JSON = None
    """Custom data attached to the connection. Not visible to other clients -
    Centrifugo never sends it - but the token carries it, visible to the user
    owning the token: put nothing in it that user must not see. The connect
    proxy's meta never reaches the client."""

    caps: list[ChannelsCapability] = field(default_factory=list)
    """Capabilities granting the connection operations in channels. Centrifugo
    PRO only."""

    labels: dict[str, str] = field(default_factory=dict)
    """The connection's client labels: for metrics, targeted server API calls
    and CEL expressions. Centrifugo PRO only."""


@dataclass(slots=True, kw_only=True)
class SubscriptionClaims:
    """The claims of a subscription token. See
    https://centrifugal.dev/docs/server/channel_token_auth."""

    user: str = ""
    """The ID of the connection's user: the "sub" claim."""

    channel: str
    """The channel the token allows to subscribe to. Required."""

    expires_at: datetime | Never
    """Until when the token is accepted: the "exp" claim, or NEVER. Required.
    The subscription expires then too, unless subscription_expires_at says
    otherwise."""

    subscription_expires_at: datetime | Never | None = None
    """When set, when the subscription expires instead of at expires_at: the
    "expire_at" claim. NEVER makes it never expire, while expires_at still
    bounds when the token is accepted: with a short expires_at, a token which
    subscribes once."""

    issued_at: datetime | None = None
    """The "iat" claim; None for now."""

    id: str = ""
    """The "jti" claim, for Centrifugo PRO's token revocation."""

    audience: str = ""
    """The "aud" claim."""

    issuer: str = ""
    """The "iss" claim."""

    info: JSON = None
    """Channel-specific information about the connection."""

    b64info: str = ""
    """Binary info in base64, instead of info."""

    data: JSON = None
    """Sent to the client in the subscribe reply."""

    b64data: str = ""
    """Binary data in base64, instead of data."""

    override: SubscribeOptionOverride | None = None
    """Channel options of the namespace overridden for this subscription."""

    allow: list[str] = field(default_factory=list)
    """Capabilities in the channel besides subscribing: "pub", "hst", "prs".
    Centrifugo PRO only."""

    server_tags_filter: FilterNode | None = None
    """Only publications whose tags match it are delivered. Centrifugo PRO only."""


def _registered(
    user: str, exp: int | None, *, issued_at: datetime | None, id_: str, audience: str, issuer: str
) -> dict[str, Any]:
    """The RFC 7519 claims Centrifugo reads, in the order the spec's vectors
    use: sub, exp, iat, jti, aud, iss."""
    w: dict[str, Any] = {"sub": user}
    if exp is not None:
        w["exp"] = exp
    w["iat"] = _unix(issued_at, "issued_at") if issued_at is not None else int(time.time())
    if id_:
        w["jti"] = id_
    if audience:
        w["aud"] = audience
    if issuer:
        w["iss"] = issuer
    return w


def connection(key: Key, claims: ConnectionClaims) -> str:
    """A connection token with claims, signed with key."""
    c = claims
    exp = _expiry(c.expires_at, "expires_at")
    if c.channels and c.subs:
        raise InvalidRequestError("token: set channels or subs, not both: Centrifugo ignores channels when subs is set")
    w = _registered(c.user, exp, issued_at=c.issued_at, id_=c.id, audience=c.audience, issuer=c.issuer)
    if (at := _session_expiry(c.connection_expires_at, "connection_expires_at")) is not None:
        w["expire_at"] = at
    if c.info is not None:
        w["info"] = _w.payload(c.info, "info")
    if c.b64info:
        w["b64info"] = c.b64info
    if c.channels:
        w["channels"] = list(c.channels)
    if c.subs:
        w["subs"] = {ch: o._to_wire() for ch, o in c.subs.items()}
    if c.meta is not None:
        w["meta"] = _w.payload(c.meta, "meta")
    if c.caps:
        w["caps"] = [cap._to_wire() for cap in c.caps]
    if c.labels:
        w["labels"] = dict(c.labels)
    return _sign(key, w)


def subscription(key: Key, claims: SubscriptionClaims) -> str:
    """A subscription token with claims, signed with key."""
    c = claims
    if not c.channel:
        raise InvalidRequestError("token: a subscription token needs a channel")
    exp = _expiry(c.expires_at, "expires_at")
    w = _registered(c.user, exp, issued_at=c.issued_at, id_=c.id, audience=c.audience, issuer=c.issuer)
    w["channel"] = c.channel
    if (at := _session_expiry(c.subscription_expires_at, "subscription_expires_at")) is not None:
        w["expire_at"] = at
    if c.info is not None:
        w["info"] = _w.payload(c.info, "info")
    if c.b64info:
        w["b64info"] = c.b64info
    if c.data is not None:
        w["data"] = _w.payload(c.data, "data")
    if c.b64data:
        w["b64data"] = c.b64data
    if c.override is not None and (o := c.override._to_wire()):
        w["override"] = o
    if c.allow:
        w["allow"] = list(c.allow)
    if c.server_tags_filter is not None and (f := c.server_tags_filter._to_wire()):
        w["server_tags_filter"] = f
    return _sign(key, w)


def _sign(key: Key, claims: dict[str, Any]) -> str:
    if not isinstance(key, Key):
        raise TypeError("token: key must be a token.Key")
    header: dict[str, str] = {"alg": key.alg, "typ": "JWT"}
    if key.kid:
        header["kid"] = key.kid
    h = json.dumps(header, separators=(",", ":")).encode()
    # A payload which is not JSON fails here, not in Centrifugo.
    p = _w.encode(claims, "token")
    signed = _b64(h) + "." + _b64(p)
    return signed + "." + _b64(key._sign(signed.encode("ascii")))


def jwks(*keys: Key) -> str:
    """The public keys of keys as a JSON Web Key Set, for Centrifugo's
    client.token.jwks_public_endpoint, which verifies tokens by their "kid".
    Each key needs an ID - see Key.with_key_id - unique in the set. HMAC keys
    have no public key to publish, and are refused, as is a set without keys.

    A set is how keys rotate without restarting Centrifugo: publish the new
    key next to the old one; once every instance of the application publishes
    it, sign with it - from a time set ahead, say; drop the old key once the
    tokens it signed have expired. Never give a key ID to another key:
    Centrifugo caches keys by ID.

    Publish the keys of client tokens and of Centrifugo PRO's server API
    tokens - see api - at separate endpoints: a token signed with any key of a
    set passes Centrifugo's signature check.
    """
    if not keys:
        raise InvalidRequestError("token: a JWKS without keys")
    out = []
    seen: set[str] = set()
    for i, k in enumerate(keys):
        if not isinstance(k, Key):
            raise TypeError(f"token: JWKS key #{i} is not a token.Key")
        if k._jwk is None:
            raise InvalidRequestError(f"token: JWKS key #{i} has no public key to publish: an HMAC key")
        if not k.kid:
            raise InvalidRequestError(f"token: JWKS key #{i} has no key ID: set one with with_key_id")
        if k.kid in seen:
            raise InvalidRequestError(f"token: JWKS key ID {k.kid!r} used twice")
        seen.add(k.kid)
        jwk = {"kty": k._jwk["kty"], "kid": k.kid, "use": "sig", "alg": k.alg}
        jwk.update({f: v for f, v in k._jwk.items() if f != "kty"})
        out.append(jwk)
    return json.dumps({"keys": out}, separators=(",", ":"))


@dataclass(slots=True, kw_only=True)
class APIClaims:
    """The claims of a token authenticating calls to Centrifugo PRO's server
    API, verified with the keys of http_api.jwks.endpoint. See
    https://centrifugal.dev/docs/pro/server_api_enhancements.

    A token passing Centrifugo PRO's checks can call every API method, and it
    checks only what it is configured to: the signature by any key of the
    JWKS endpoint, and audience, issuer and scope only when http_api.jwks sets
    them. So the token must carry a claim no other token carries - above all
    the connection and subscription tokens users hold:

    - sign API tokens with keys of their own, published at their own JWKS
      endpoint - never the one of client.token.jwks_public_endpoint;
    - set audience, scope or both, to values only API tokens carry, and
      configure http_api.jwks.audience and scope to require them. api refuses
      claims with neither.
    """

    audience: str = ""
    """The "aud" claim: http_api.jwks.audience."""

    scope: list[str] = field(default_factory=list)
    """The "scope" claim, its scopes joined by spaces: http_api.jwks.scope is
    one of them."""

    issuer: str = ""
    """The "iss" claim: http_api.jwks.issuer."""

    subject: str = ""
    """The "sub" claim: who calls the API, for the application's own logs."""

    expires_at: datetime | None = None
    """When the token expires: required, best minutes ahead. Centrifugo PRO
    would accept a token without "exp" for as long as its key is published, so
    api never signs one."""

    issued_at: datetime | None = None
    """The "iat" claim; None for now."""

    id: str = ""
    """The "jti" claim."""


def api(key: Key, claims: APIClaims) -> str:
    """A token for Centrifugo PRO's server API with claims, signed with key - an
    asymmetric key with an ID, published by jwks: Centrifugo PRO finds it by
    the "kid". See APIClaims for keeping it apart from client tokens, and
    APITokens for one to send with every call."""
    c = claims
    if not isinstance(key, Key):
        raise TypeError("token: key must be a token.Key")
    if key._jwk is None:
        raise InvalidRequestError(
            "token: an API token needs an RSA, ECDSA or Ed25519 key: "
            "Centrifugo PRO verifies it with the public keys of its JWKS endpoint"
        )
    if not key.kid:
        raise InvalidRequestError(
            "token: an API token needs a key ID, by which Centrifugo PRO finds the key: use with_key_id"
        )
    if not c.audience and not c.scope:
        raise InvalidRequestError(
            "token: set audience or scope, required by http_api.jwks, "
            "so that client tokens signed with the same keys can't call the server API"
        )
    if c.expires_at is None:
        raise InvalidRequestError(
            "token: set expires_at: Centrifugo PRO accepts an API token without one while its key is published"
        )
    for s in c.scope:
        if not s or any(ch in s for ch in " \t\n"):
            raise InvalidRequestError("token: a scope is empty or has a space")
    w = _registered(
        c.subject,
        _unix(c.expires_at, "expires_at"),
        issued_at=c.issued_at,
        id_=c.id,
        audience=c.audience,
        issuer=c.issuer,
    )
    if c.scope:
        w["scope"] = " ".join(c.scope)
    return _sign(key, w)


class APITokens:
    """Issues the tokens a Client sends to Centrifugo PRO: its token method is
    the client's bearer_token_func. It signs a token with api and reuses it for
    half its lifetime, so a token sent has at least half of it left. Safe for
    concurrent use.

    >>> tokens = token.APITokens(key=api_key,   # its own key, not the client tokens'
    ...     claims=token.APIClaims(audience="centrifugo-api", scope=["centrifugo:api"]))
    >>> client = cent.Client("https://centrifugo.example.com/api", bearer_token_func=tokens.token)

    current_key, when set, returns the key to sign each new token with instead
    of key - the key active now, when keys rotate. A key must be published in
    the JWKS before it signs: Centrifugo PRO refuses a token whose key it can't
    find. claims must leave expires_at and issued_at unset: the tokens are
    issued when needed and expire ttl seconds later (300 by default).
    """

    def __init__(
        self,
        *,
        claims: APIClaims,
        key: Key | None = None,
        current_key: Callable[[], Key] | None = None,
        ttl: float = 300.0,
    ) -> None:
        if (key is None) == (current_key is None):
            raise InvalidRequestError("token: APITokens takes key or current_key, one of them")
        if claims.expires_at is not None or claims.issued_at is not None:
            raise InvalidRequestError(
                "token: APITokens sets expires_at and issued_at itself: leave them unset, and set ttl"
            )
        if isinstance(ttl, bool) or not isinstance(ttl, (int, float)) or ttl <= 0:
            raise InvalidRequestError("token: APITokens ttl must be a positive number of seconds")
        self._claims = claims
        self._key = key
        self._current_key = current_key
        self._ttl = float(ttl)
        self._lock = threading.Lock()
        self._token = ""
        self._refresh_at = 0.0

    def token(self) -> str:
        """A token valid for at least half of ttl, signing a new one when the
        previous one has less left."""
        with self._lock:
            now = time.time()
            if self._token and now < self._refresh_at:
                return self._token
            key = self._current_key() if self._current_key is not None else self._key
            if key is None:  # pragma: no cover - one of them is set, see __init__
                raise InvalidRequestError("token: APITokens without a key")
            issued = datetime.fromtimestamp(now, UTC)
            c = APIClaims(
                audience=self._claims.audience,
                scope=list(self._claims.scope),
                issuer=self._claims.issuer,
                subject=self._claims.subject,
                id=self._claims.id,
                issued_at=issued,
                expires_at=datetime.fromtimestamp(now + self._ttl, UTC),
            )
            self._token = api(key, c)
            self._refresh_at = now + self._ttl / 2
            return self._token
