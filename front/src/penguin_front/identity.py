"""Who is signed in: the development identity, `GET /signin`, the cookie read and extended on
every request, `GET /api/me`, and the check of the current group (README-details.md, "The
development identity", "The cookie", "Groups and the current group").

- `signed_in()` gives the signed-in user's `Identity`, read from the cookie and from nowhere
  else, or refuses `401` `front.not_signed_in`. An answer to a request whose cookie was last
  used more than `COOKIE_EXTEND_AFTER_S` ago carries a new cookie moving the thirty days on.
- `current_group(identity)` gives the current group's id from `X-PenguinSlicer-Group` or, on
  a `GET`, the query parameter `group`, accepted only when the cookie lists it; otherwise
  `403` `front.group_not_allowed` and a `refused` line. A request that acts for a group is
  marked by `acts_for_group`, so the tests find every one of them by themselves.
"""

from flask import g, redirect, request

from .context import context
from .cookie import (COOKIE_EXTEND_AFTER_S, COOKIE_LIFETIME_S, COOKIE_NAME,
                     COOKIE_SIZE_LINE_BYTES, Identity)
from .errors import FrontError

#: The development identity's four fixed values (README-details.md, "Running phase 2 on one
#: machine"), so that a configuration can be written by hand for its group.
DEV_IDENTITY = Identity("dev-user", "Development User",
                        (("dev-group", "Development Group"),), None, 0)
GROUP_HEADER = "X-PenguinSlicer-Group"
GROUP_PARAMETER = "group"
#: The most of a value from the browser a refusal line holds.
_LINE_VALUE_CHARS = 200


def register(app):
    app.add_url_rule("/signin", "signin", signin, methods=["GET"])
    app.add_url_rule("/api/me", "me", me, methods=["GET"])


def signin():
    """`GET /signin`: with the development identity on, its cookie at once and straight to
    `return`; signing in with Onshape is phase 3's."""
    ctx = context()
    if not ctx["settings"].dev_identity:
        raise FrontError("front.no_such_request",
                         "GET /signin: signing in with Onshape is built in phase 3, and the "
                         "development identity is off")
    identity = DEV_IDENTITY.used(ctx["clock"].now())
    response = redirect(safe_return(request.args.get("return", "")), 302)
    set_cookie_for(response, identity)
    ctx["log"].write("sign_in", user_key=identity.user_id, user_name=identity.user_name,
                     groups=[{"id": gid, "name": name} for gid, name in identity.groups],
                     dev_identity=True)
    return response


def safe_return(value):
    """`value` when it is a path of this site (a single leading `/`, no backslash, which a
    browser reads as a slash, and no control character); otherwise `/`."""
    if not value.startswith("/") or value.startswith("//") or "\\" in value \
            or any(ord(c) < 0x20 or ord(c) == 0x7f for c in value):
        return "/"
    return value


def me():
    """`GET /api/me`: the signed-in user and their groups, from the cookie alone."""
    identity = signed_in()
    return {"user": {"id": identity.user_id, "name": identity.user_name},
            "groups": [{"id": gid, "name": name} for gid, name in identity.groups]}


def identity_or_none():
    """The signed-in user's `Identity`, or None; notes a cookie due to be extended."""
    if "penguin_identity" not in g:
        ctx = context()
        now = ctx["clock"].now()
        identity = ctx["cookie_key"].open(request.cookies.get(COOKIE_NAME, ""), now)
        g.penguin_identity = identity
        if identity is not None and now - identity.used_at > COOKIE_EXTEND_AFTER_S:
            g.penguin_extend = identity.used(now)
    return g.penguin_identity


def signed_in():
    identity = identity_or_none()
    if identity is None:
        raise FrontError("front.not_signed_in",
                         f"{request.method} {request.path}: no cookie this front server can "
                         "read and in date")
    return identity


def acts_for_group(view):
    """Mark `view` as a request that acts for a group."""
    view.penguin_acts_for_group = True
    return view


def current_group(identity):
    """The current group's id, accepted only when the cookie lists it."""
    header = request.headers.get(GROUP_HEADER)
    query = request.args.get(GROUP_PARAMETER) if request.method in ("GET", "HEAD") else None
    named = header if header is not None else query
    why = None
    if header is not None and query is not None and header != query:
        why = "the header and the query name different groups"
    elif named is None or named == "":
        why = "no group named"
    elif identity.group_name(named) is None:
        why = "a group the cookie does not list"
    if why is not None:
        shown = {"header": _cut(header), "query": _cut(query)}
        context()["log"].write("refused", reason="group_not_allowed", why=why,
                               user_key=identity.user_id, method=request.method,
                               path=request.path, **shown)
        raise FrontError("front.group_not_allowed",
                         f"{request.method} {request.path}: {why}")
    g.penguin_group = named
    return named


def _cut(value):
    return value if value is None else value[:_LINE_VALUE_CHARS]


def set_cookie_for(response, identity):
    """Set the cookie holding `identity` on `response`, writing a line when it is large."""
    ctx = context()
    value = ctx["cookie_key"].seal(identity)
    hosted = ctx["settings"].base_url.startswith("https://")
    response.set_cookie(COOKIE_NAME, value, max_age=COOKIE_LIFETIME_S, path="/",
                        httponly=True, secure=hosted, samesite="None" if hosted else "Lax")
    size = len(COOKIE_NAME) + 1 + len(value)
    if size > COOKIE_SIZE_LINE_BYTES:
        ctx["log"].write("cookie_large", bytes=size, user_key=identity.user_id,
                         groups=len(identity.groups))
    return response


def extend_cookie(response):
    """After every answer: the new cookie moving the thirty days on, when one is due and the
    answer does not already set the cookie."""
    extended = g.get("penguin_extend")
    if extended is not None and not any(value.startswith(COOKIE_NAME + "=") for value in
                                        response.headers.getlist("Set-Cookie")):
        set_cookie_for(response, extended)
    return response
