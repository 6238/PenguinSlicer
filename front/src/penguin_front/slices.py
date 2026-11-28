"""`POST /api/slices`: submitting a plate configuration (README-details.md, "Submitting a
plate configuration"; contracts/wizard-front-server.md, "`POST /api/slices`").

- It needs a signed-in user and acts for the current group, which is noted beside the slice
  job: in its record in the state bucket (state `submitted`), and in the following's memory.
  A record that cannot be written is no error for the page.
- A body over `MAX_PLATE_CONFIGURATION_BYTES` is refused `413` before it is read, with the
  slice service's report for that limit; a body without `Content-Length` is read no further
  than one byte past the limit.
- Each user may submit `SUBMISSIONS_PER_MINUTE` plate configurations in any minute; past
  that, `429` `front.too_many_requests` with `Retry-After`. A refused submission does not
  count.
- The body passes to the slice service's `POST /slices` unchanged, with the cookie's user
  key; the slice service judges its form. Its `202` becomes the contract's answer
  (`{"slice": {"id", "plate_id", "submission_id", "progress"}}`), and the slice job is
  followed. Every refusal of the slice service, `slice.part_missing`, `slice.busy` and the
  stopping answer `slice.stopping` among them, reaches the page unchanged: the front server
  holds no submission back for later.
- A repeat is recognised by the slice service, by the user key and `submission_id`, and
  answered with the first attempt's slice job, which is followed once.
"""

import re

from flask import request

from . import sliced
from .context import context
from .errors import FrontError
from .identity import acts_for_group, current_group, signed_in
from .parts import passed
from .slice_client import SliceUnreachable, json_object, refusal, user_key_header

#: The largest plate configuration, in bytes (the plate configuration's contract,
#: *proposed* there).
MAX_PLATE_CONFIGURATION_BYTES = 1_048_576
#: Submissions one user may make in any minute (*proposed*).
SUBMISSIONS_PER_MINUTE = 30
_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")


def register(app):
    app.add_url_rule("/api/slices", "submit_slice", submit, methods=["POST"])


def over_size(detail):
    """The slice service's own report for a plate configuration over the limit, exactly as
    contracts/examples/error-report-plate-configuration-over-size.json holds it for a
    `Content-Length` of 1,048,577 bytes."""
    return {
        "code": "slice.bad_plate_configuration",
        "message": "This plate configuration could not be read: it is larger than 1,048,576 "
                   "bytes.",
        "where": {"stage": "checking"},
        "remedy": "Lay out the plate again and send a new slice.",
        "retryable": False,
        "detail": detail,
    }


@acts_for_group
def submit():
    ctx = context()
    identity = signed_in()
    group = current_group(identity)
    limit = MAX_PLATE_CONFIGURATION_BYTES
    length = request.content_length
    if length is not None and length > limit:
        raise passed(413, over_size(f"plate configuration Content-Length {length:,} bytes, "
                                    f"cap {limit:,}"))
    wait = ctx["submissions"].take(identity.user_id)
    if wait is not None:
        raise FrontError("front.too_many_requests",
                         f"more than {ctx['submissions_per_minute']} plate configurations "
                         "submitted in a minute", headers={"Retry-After": str(wait)})
    body = request.stream.read(limit + 1) if length is None else request.get_data()
    if len(body) > limit:
        raise passed(413, over_size(f"a plate configuration of more than {limit:,} bytes, "
                                    "sent without Content-Length"))
    try:
        raw = ctx["slice"].send("POST", "/slices", content=body, headers={
            **user_key_header(identity.user_id), "Content-Type": "application/json"})
    except SliceUnreachable as exc:
        raise FrontError("front.slice_unreachable", str(exc)) from None
    if raw.status != 202:
        raise refusal(raw, "POST /slices")
    accepted = _accepted(raw.body)
    job = accepted["job"]
    why = sliced.note_submitted(ctx["state_bucket"], identity.user_id, job, group,
                                ctx["clock"].now())
    if why is not None:
        ctx["log"].write("slice_record_unwritten", user_key=identity.user_id, group=group,
                         slice=job, why=why)
    follower = ctx["follower"]
    started = follower.follow(identity.user_id, job, group)
    progress = follower.as_pages_see(identity.user_id, job, accepted["progress"])
    ctx["log"].write("slice_submitted", user_key=identity.user_id, group=group, slice=job,
                     plate_id=accepted.get("plate_id"),
                     submission_id=accepted.get("submission_id"), state=progress.get("state"),
                     repeat=not started)
    return {"slice": {"id": job, "plate_id": accepted.get("plate_id"),
                      "submission_id": accepted.get("submission_id"),
                      "progress": progress}}, 202


def _accepted(body):
    """The slice service's `202`, checked for what the front server reads of it."""
    accepted = json_object(body)
    if accepted is None or not isinstance(accepted.get("job"), str) \
            or not _ID.fullmatch(accepted["job"]) \
            or not isinstance(accepted.get("progress"), dict):
        raise RuntimeError(f"POST /slices: the slice service's 202 is not a slice job: "
                           f"{body[:200]!r}")
    return accepted
