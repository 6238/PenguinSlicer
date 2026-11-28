"""The page's reports about itself (README-details.md, "The page's reports about itself";
contracts/wizard-front-server.md, "The page's reports about itself").

`POST /api/reports/failure` and `POST /api/reports/drawing` each write one log line,
component `wizard` (`failure_report`, `drawing_report`), and answer `204` with no body.

- A report comes from a browser like any other request, so only the contract's fields are
  written, in its order: each string cut to its length, each enumerated value checked
  against its list. A required field missing, of the wrong kind, or off its list is
  refused `400` `front.bad_request`; an optional field of the wrong kind is dropped;
  anything else the report carries is dropped. A drawing summary of the Layout view drops
  the fields that go only with the Preview step.
- It needs a signed-in user. The group is written when the page names one of the user's;
  a report is never refused for its group, and one naming another is written without it.
  The page's version is written when `X-PenguinSlicer-Page` has the version's form.
- Each page is held to `REPORTS_PER_PAGE_PER_MINUTE` reports in any minute, counted for the
  signed-in user and the report's `page`; past it, `429` `front.too_many_reports`, which the
  page drops. A refused report is not counted.
"""

import math
import re

from flask import Response, request

from .answers import json_body
from .context import context
from .errors import FrontError
from .identity import GROUP_HEADER, signed_in
from .ratelimit import RateLimit
from .version import is_version

#: Reports one page may send in any minute (*proposed*).
REPORTS_PER_PAGE_PER_MINUTE = 6
#: The longest `page` written (*proposed*: the contract gives no length; a page's random id
#: is a UUID of 36 characters).
PAGE_CHARS = 64
#: The largest report read (*proposed*): a whole report with its longest strings is under
#: 2 KB, so a body larger than this is no honest report and is refused before it is read.
MAX_REPORT_BYTES = 16_384
_SHA256 = re.compile(r"[0-9a-f]{64}")

WHAT = ("part_not_drawable", "storage_refused", "storage_cleared", "drawing_context_lost",
        "layout_failed", "page_failed")
STEP = ("parts", "settings", "advanced", "layout", "preview", "send", "none")
VIEW = ("layout", "preview")
DRAWING = ("graphics_card", "software")


def _text(length):
    def check(value):
        return value[:length] if isinstance(value, str) else _Bad
    return check


def _page(value):
    return value[:PAGE_CHARS] if isinstance(value, str) and value else _Bad


def _one_of(allowed):
    def check(value):
        return value if isinstance(value, str) and value in allowed else _Bad
    return check


def _flag(value):
    return value if isinstance(value, bool) else _Bad


def _number(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool) \
            and math.isfinite(value):
        return value
    return _Bad


def _hash(value):
    return value if isinstance(value, str) and _SHA256.fullmatch(value) else _Bad


class _Bad:
    """A value of the wrong kind, or off its list."""


REQUIRED, OPTIONAL, PREVIEW = "required", "optional", "with preview"

#: Each kind's fields, in the contract's order: (name, check, when).
FIELDS = {
    "failure": (
        ("page", _page, REQUIRED), ("what", _one_of(WHAT), REQUIRED),
        ("step", _one_of(STEP), REQUIRED), ("browser", _text(40), REQUIRED),
        ("browser_version", _text(40), REQUIRED), ("software_3d", _flag, REQUIRED),
        ("part_sha256", _hash, OPTIONAL), ("detail", _text(1000), OPTIONAL),
    ),
    "drawing": (
        ("page", _page, REQUIRED), ("view", _one_of(VIEW), REQUIRED),
        ("fps_typical", _number, REQUIRED), ("fps_worst", _number, REQUIRED),
        ("first_layer_ms", _number, PREVIEW), ("longest_hold_ms", _number, REQUIRED),
        ("instances", _number, REQUIRED), ("sliced_file_bytes", _number, PREVIEW),
        ("sliced_file_lines", _number, PREVIEW), ("browser", _text(40), REQUIRED),
        ("browser_version", _text(40), REQUIRED), ("os", _text(40), REQUIRED),
        ("drawing", _one_of(DRAWING), REQUIRED), ("graphics_card", _text(120), OPTIONAL),
        ("processors", _number, OPTIONAL), ("memory_gb", _number, OPTIONAL),
        ("panel_width_px", _number, REQUIRED), ("pixel_ratio", _number, REQUIRED),
        ("in_onshape", _flag, REQUIRED),
    ),
}
EVENTS = {"failure": "failure_report", "drawing": "drawing_report"}


def register(app):
    app.add_url_rule("/api/reports/failure", "report_failure", lambda: _report("failure"),
                     methods=["POST"])
    app.add_url_rule("/api/reports/drawing", "report_drawing", lambda: _report("drawing"),
                     methods=["POST"])
    app.extensions["penguin_front"]["reports"] = RateLimit(
        app.extensions["penguin_front"]["clock"], REPORTS_PER_PAGE_PER_MINUTE)


def _report(kind):
    ctx = context()
    identity = signed_in()
    limit, length = MAX_REPORT_BYTES, request.content_length
    if length is not None and length > limit:
        raise FrontError("front.bad_request", f"a {kind} report of {length:,} bytes, over "
                                              f"the {limit:,} a report may hold")
    # Read no further than one byte past the limit; the rest is never read.
    raw = request.stream.read(limit + 1) if length is None else request.get_data()
    if len(raw) > limit:
        raise FrontError("front.bad_request", f"a {kind} report of more than {limit:,} "
                                              "bytes, sent without Content-Length")
    body = json_body(raw)
    if not isinstance(body, dict):
        raise FrontError("front.bad_request", f"a {kind} report that is not a JSON object")
    fields = _fields(kind, body)
    if ctx["reports"].take((identity.user_id, fields["page"])) is not None:
        raise FrontError("front.too_many_reports",
                         f"more than {REPORTS_PER_PAGE_PER_MINUTE} reports from page "
                         f"{fields['page']} in a minute")
    line = {"user_key": identity.user_id}
    group = request.headers.get(GROUP_HEADER)
    if group and identity.group_name(group) is not None:
        line["group"] = group
    page_version = request.headers.get("X-PenguinSlicer-Page", "")
    if is_version(page_version):
        line["page_version"] = page_version
    ctx["log"].write_as("wizard", EVENTS[kind], **line, **fields)
    return Response(status=204)


def _fields(kind, body):
    """The report's fields as written, in the contract's order; `front.bad_request` naming
    the first required field missing, of the wrong kind or off its list."""
    preview = body.get("view") == "preview"
    fields = {}
    for name, check, when in FIELDS[kind]:
        if when == PREVIEW and not preview:
            continue
        value = check(body[name]) if name in body else _Bad
        if value is _Bad:
            if when == OPTIONAL:
                continue
            raise FrontError("front.bad_request",
                             f"a {kind} report whose {name} is missing, of the wrong kind or "
                             "off its list")
        fields[name] = value
    return fields
