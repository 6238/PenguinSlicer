"""`GET /api/settings-table`: the table of settings, with the profile catalog's names, as the
slice service that is running supplies it (README-details.md, "The table of settings").

The front server asks the slice service each time and keeps no copy, in memory or anywhere
else, since the slice service is deployed separately and a new Orca version changes the
table under a running front server. The answer passes unchanged and whole: compressed as
the slice service compressed it when the browser accepts gzip (the front server then asks
for gzip), and plain otherwise. It needs a signed-in user and acts for no group. A slice
service that does not answer is `503` `front.slice_unreachable`; one that answers with its
own error report has it passed byte for byte with its status.
"""

import re

from flask import Response, request

from .context import context
from .errors import FrontError
from .identity import signed_in
from .slice_client import SliceUnreachable, refusal

PATH = "/settings-table"
_WEIGHT = re.compile(r"[0-9.]+")


def register(app):
    app.add_url_rule("/api/settings-table", "settings_table", settings_table,
                     methods=["GET"])


def accepts_gzip(header):
    """Whether an `Accept-Encoding` header accepts gzip: gzip named with a weight above zero,
    or, when gzip is not named, `*` with a weight above zero (RFC 9110, 12.5.3: a coding
    named explicitly overrides `*`)."""
    weights = {}
    for item in header.split(","):
        coding, *parameters = item.split(";")
        coding = coding.strip().lower()
        if coding not in ("gzip", "*"):
            continue
        weight = _weight(parameters)
        if weight is None:
            continue
        # A coding named twice takes its highest weight.
        weights[coding] = max(weight, weights.get(coding, 0.0))
    return weights.get("gzip", weights.get("*", 0.0)) > 0


def _weight(parameters):
    """The weight an item's parameters give it: its `q` (a name in any case), 1 when it has
    none, or None when its `q` is not a number. Parameters other than `q` are passed over."""
    weight = 1.0
    for parameter in parameters:
        name, _, value = parameter.partition("=")
        if name.strip().lower() == "q":
            value = value.strip()
            if _WEIGHT.fullmatch(value) is None:
                return None
            try:
                weight = float(value)
            except ValueError:
                return None
    return weight


def settings_table():
    signed_in()
    gzip_ok = accepts_gzip(request.headers.get("Accept-Encoding", ""))
    try:
        raw = context()["slice"].get_raw(PATH, headers={
            "Accept-Encoding": "gzip" if gzip_ok else "identity"})
    except SliceUnreachable as exc:
        raise FrontError("front.slice_unreachable", str(exc)) from None
    encoding = raw.headers.get("Content-Encoding")
    if raw.status == 200:
        response = Response(raw.body, 200,
                            content_type=raw.headers.get("Content-Type", "application/json"))
        if encoding is not None:
            response.headers["Content-Encoding"] = encoding
        response.headers["Vary"] = "Accept-Encoding"
        return response
    raise refusal(raw, f"GET {PATH}")
