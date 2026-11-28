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

import json
import re

from flask import Response, request

from .context import context
from .errors import FrontError, PassedReport
from .identity import signed_in
from .slice_client import SliceUnreachable

PATH = "/settings-table"
_CODING = re.compile(r"\s*([^;\s]+)\s*(?:;\s*q\s*=\s*([0-9.]+))?\s*")


def register(app):
    app.add_url_rule("/api/settings-table", "settings_table", settings_table,
                     methods=["GET"])


def accepts_gzip(header):
    """Whether an `Accept-Encoding` header accepts gzip: named, or `*`, with a weight above
    zero."""
    for item in header.split(","):
        match = _CODING.fullmatch(item)
        if match is None or match[1].lower() not in ("gzip", "*"):
            continue
        try:
            weight = float(match[2]) if match[2] is not None else 1.0
        except ValueError:
            continue
        if weight > 0:
            return True
    return False


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
    report = _report(raw.body) if encoding is None else None
    if report is None:
        raise RuntimeError(f"GET {PATH}: the slice service answered {raw.status} with neither "
                           f"the table nor its own error report: {raw.body[:200]!r}")
    raise PassedReport(raw.status, raw.body, report)


def _report(body):
    """The slice service's error report in `body`, or None."""
    try:
        report = json.loads(body)
    except ValueError:
        return None
    if isinstance(report, dict) and isinstance(report.get("code"), str) \
            and report["code"].startswith("slice."):
        return report
    return None
