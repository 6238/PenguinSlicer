"""`POST /api/parts`: one part, uploaded by the page at the moment the user adds it, passed to
the slice service with the user key (README-details.md, "The user key" and "Parts";
contracts/wizard-front-server.md, "`POST /api/parts`").

- It needs a signed-in user and acts for the current group (for the log and the check).
- A `Content-Length` over `MAX_PART_BYTES` is refused `413` before the body is read, with
  the slice service's own report for that limit, `slice.part_too_detailed`; no
  `Content-Length` is `400` `front.bad_request`.
- Each user may upload `PART_UPLOADS_PER_MINUTE` parts in any minute; past that, `429`
  `front.too_many_requests` with `Retry-After`. A refused upload does not count.
- The body passes to the slice service's `POST /parts?units=` in pieces of at most
  `PIECE_BYTES`, never held whole, with the cookie's user key and the page's `units` as
  sent; the front server keeps no copy and changes no byte. The slice service's answer
  reaches the page unchanged: `201` with the part's record, or its refusal.
"""

import json

from flask import Response, request

from .context import context
from .errors import FrontError, PassedReport
from .identity import acts_for_group, current_group, signed_in
from .slice_client import SliceUnreachable, json_object, refusal, user_key_header

#: The largest part, in bytes: the plate configuration's limit for one part (150,000
#: triangles of a binary STL).
MAX_PART_BYTES = 7_500_084
#: Uploads one user may make in any minute (*proposed*): a part set of 25 parts uploaded
#: again after a restart of the slice service, with room to spare.
PART_UPLOADS_PER_MINUTE = 120
#: The most of an upload's body the front server reads ahead of what it has passed on.
PIECE_BYTES = 64 * 1024


def register(app):
    app.add_url_rule("/api/parts", "upload_part", upload_part, methods=["POST"])


def over_size(length):
    """The slice service's own report for a part over the limit, exactly as
    contracts/examples/error-report-part-over-size.json holds it for 7,500,085 bytes."""
    return {
        "code": "slice.part_too_detailed",
        "message": "This part is too detailed to print here (over 7,500,084 bytes, the size "
                   "of 150,000 triangles).",
        "where": {"stage": "checking"},
        "remedy": "Export the part with a coarser tessellation, or simplify it, and add it "
                  "again.",
        "retryable": False,
        "detail": f"upload Content-Length {length:,} bytes, cap {MAX_PART_BYTES:,}",
    }


def passed(status, report):
    """A report of the slice service's that the front server answers itself, in the form the
    slice service writes its reports (`json.dumps` of the report, fields in order)."""
    body = json.dumps(report).encode()
    return PassedReport(status, body, report)


@acts_for_group
def upload_part():
    ctx = context()
    identity = signed_in()
    group = current_group(identity)
    length = request.content_length
    if length is None:
        raise FrontError("front.bad_request", "an upload of a part without Content-Length")
    if length > MAX_PART_BYTES:
        raise passed(413, over_size(length))
    wait = ctx["part_uploads"].take(identity.user_id)
    if wait is not None:
        raise FrontError("front.too_many_requests",
                         f"more than {ctx['part_uploads_per_minute']} uploads of parts in a "
                         "minute", headers={"Retry-After": str(wait)})
    params = {"units": request.args["units"]} if "units" in request.args else None
    headers = {**user_key_header(identity.user_id), "Content-Length": str(length),
               "Content-Type": "application/octet-stream"}
    try:
        raw = ctx["slice"].send("POST", "/parts", headers=headers, params=params,
                                content=_pieces(request.stream, length))
    except SliceUnreachable as exc:
        raise FrontError("front.slice_unreachable", str(exc)) from None
    if raw.status != 201:
        raise refusal(raw, "POST /parts")
    _log_upload(ctx["log"], identity.user_id, group, raw.body, length)
    return Response(raw.body, 201, content_type="application/json")


def _pieces(stream, length):
    """The body read in pieces of at most `PIECE_BYTES`, `length` bytes in all."""
    left = length
    while left > 0:
        piece = stream.read(min(PIECE_BYTES, left))
        if not piece:
            raise FrontError("front.bad_request",
                             f"the upload ended {left:,} bytes short of its Content-Length")
        left -= len(piece)
        yield piece


def _log_upload(log, user_key, group, body, length):
    """The `part_uploaded` line, from the record as the slice service gave it; a field the
    record lacks is written as null, since the record itself passes to the page unchanged."""
    record = json_object(body) or {}
    measurements = record.get("measurements")
    measurements = measurements if isinstance(measurements, dict) else {}
    warnings = record.get("warnings")
    log.write("part_uploaded", user_key=user_key, group=group, sha256=record.get("sha256"),
              units=record.get("units"), bytes=length,
              triangles=measurements.get("triangles"),
              warnings=len(warnings) if isinstance(warnings, list) else 0)
