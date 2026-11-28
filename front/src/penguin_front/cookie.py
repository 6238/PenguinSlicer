"""The cookie: the whole of a sign-in, encrypted and authenticated with the cookie key
(README-details.md, "The cookie").

The cookie holds the user's Onshape id and name, each of their groups by id and name in a
fixed order, the two tokens Onshape issued (none for the development identity), the time of
its last use and a format number, as one JSON object. `CookieKey.seal` encrypts it with
AES-256-GCM under a key derived from the cookie key by HKDF-SHA256, a fresh 12-byte random
nonce each time, and writes nonce and ciphertext as unpadded base64url; `CookieKey.open`
gives the `Identity` back, or None for anything that is not a cookie this front server made
and can still read: text of the wrong form, a cookie changed by one bit, one made with
another key, one of a format it does not read, or one unused for `COOKIE_LIFETIME_S`.
Nothing about a sign-in is kept on the server.
"""

import base64
import binascii
import json
import os
from dataclasses import dataclass, replace

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

COOKIE_NAME = "penguinslicer"
#: A sign-in lasts thirty days from its last use.
COOKIE_LIFETIME_S = 2_592_000
#: An answer moves the thirty days on only when more than a day has passed since the
#: cookie's last-use time, so that most answers carry no Set-Cookie.
COOKIE_EXTEND_AFTER_S = 86_400
#: A cookie set larger than this writes a line with its size: browsers drop a cookie over
#: about 4 KB without a word.
COOKIE_SIZE_LINE_BYTES = 3_800
#: The cookie's format. A cookie of every format up to this one is read.
COOKIE_FORMAT = 1
#: What the key is derived for, so the same secret could never serve as another key.
_KEY_INFO = b"penguinslicer cookie key"
_NONCE_BYTES = 12
#: A cookie longer than this is no cookie of ours: far above any a browser keeps.
_MAX_TEXT = 8_192


@dataclass(frozen=True)
class Identity:
    """Who is signed in: the user key and name, the groups as (id, name) pairs in their
    fixed order, Onshape's tokens (None for the development identity), and the cookie's
    last-use time in whole seconds since the epoch."""

    user_id: str
    user_name: str
    groups: tuple
    tokens: dict | None
    used_at: int

    def used(self, moment):
        """The same sign-in, last used at `moment`."""
        return replace(self, used_at=int(moment))

    def group_name(self, group_id):
        """The name of the group `group_id`, or None when the cookie does not list it."""
        for listed, name in self.groups:
            if listed == group_id:
                return name
        return None


class CookieKey:
    """The cookie key: `secret` is the setting's text, or bytes made at start."""

    def __init__(self, secret):
        material = secret.encode() if isinstance(secret, str) else bytes(secret)
        derived = HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
                       info=_KEY_INFO).derive(material)
        self._aead = AESGCM(derived)

    def seal(self, identity):
        return self.seal_fields({
            "format": COOKIE_FORMAT,
            "user": {"id": identity.user_id, "name": identity.user_name},
            "groups": [{"id": gid, "name": name} for gid, name in identity.groups],
            "tokens": identity.tokens,
            "used_at": identity.used_at,
        })

    def seal_fields(self, fields):
        return self.seal_bytes(json.dumps(fields, separators=(",", ":")).encode())

    def seal_bytes(self, plain):
        nonce = os.urandom(_NONCE_BYTES)
        sealed = nonce + self._aead.encrypt(nonce, plain, None)
        return base64.urlsafe_b64encode(sealed).decode().rstrip("=")

    def open(self, text, now):
        """The `Identity` the cookie holds, or None if it is no sign-in at `now`."""
        if not text or len(text) > _MAX_TEXT or not text.isascii():
            return None
        try:
            sealed = base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
        except (binascii.Error, ValueError):
            return None
        if len(sealed) <= _NONCE_BYTES:
            return None
        try:
            plain = self._aead.decrypt(sealed[:_NONCE_BYTES], sealed[_NONCE_BYTES:], None)
            fields = json.loads(plain)
        except (InvalidTag, ValueError):
            return None
        identity = _identity(fields)
        if identity is None or now - identity.used_at >= COOKIE_LIFETIME_S:
            return None
        return identity


def _text(value):
    return isinstance(value, str) and value != ""


def _whole(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _identity(fields):
    """The `Identity` of a cookie's opened fields, or None for a format or shape this front
    server does not read."""
    if not isinstance(fields, dict):
        return None
    format_number, user, groups = fields.get("format"), fields.get("user"), fields.get("groups")
    if not _whole(format_number) or not 1 <= format_number <= COOKIE_FORMAT \
            or not _whole(fields.get("used_at")) or not isinstance(user, dict) \
            or not _text(user.get("id")) or not isinstance(user.get("name"), str) \
            or not isinstance(groups, list) or not groups \
            or not all(isinstance(g, dict) and _text(g.get("id")) and
                       isinstance(g.get("name"), str) for g in groups):
        return None
    tokens = fields.get("tokens")
    return Identity(user["id"], user["name"], tuple((g["id"], g["name"]) for g in groups),
                    tokens if isinstance(tokens, dict) else None, fields["used_at"])
