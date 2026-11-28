"""Asking about a slice job, and its sliced file's details and the sliced file
(README-details.md, "Asking about a slice job", "The sliced file's details and the sliced
file" and "Two hours, the sweep, and the backstop"; contracts/wizard-front-server.md, "Asking
about a slice job" and "The sliced file").

`reckon(slice)` is the slice job's latest report as the front server reckons it, the one
answer every request about a slice job starts from. It needs a signed-in user and the current
group, refuses an id of another form `404` `front.slice_unknown` before it asks anyone, then
looks in the state bucket, and only then asks the slice service:

- a `stored` record whose sliced file is not due and is there: its `done` report, carrying
  the sliced file's details;
- a `stored` record whose sliced file is due, or gone from the state bucket: the file is
  deleted and the record turned `expired`, and the answer is the expired report (the `done`
  report turned `failed`, `sequence` one more, `front.sliced_file_expired`); a delete that
  fails leaves the record for the sweep, and the answer is the same;
- an `expired` record: the expired report for `EXPIRED_RECORD_KEPT_S` after it expired,
  then unknown;
- a `failed` record (a sliced file over 50 MB): its `failed` report;
- otherwise the slice service's latest report (`GET /slices/<job>`), as pages see it: a
  `done` held back until its file is stored. A slice job not yet final that the front
  server does not follow (a front server started since it was submitted) is followed from
  here, with its record's group, or else the current group, so that it is stored.

Unknown to both, or another user's: `404` `front.slice_unknown`, with a `refused` line. A
state bucket that does not answer is `503` `front.state_bucket_unreachable`; a slice service
that does not answer, when the state bucket holds no record that answers, `503`
`front.slice_unreachable`.
"""

import re
from dataclasses import dataclass

from flask import Response, request

from . import sliced
from .buckets import BucketUnavailable, NotFound
from .context import context
from .errors import FrontError
from .following import FINAL_STATES
from .identity import acts_for_group, current_group, signed_in
from .slice_client import SliceUnreachable, json_object, refusal, slice_report, user_key_header

_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")
#: The characters a sliced file's name keeps in `Content-Disposition`: those its contract
#: makes it of (contracts/sliced-file.md, "Name"), and `.` and `+`.
_SAFE_NAME = re.compile(r"[A-Za-z0-9._+-]{1,200}")


def register(app):
    app.add_url_rule("/api/slices/<slice>", "ask_slice", ask, methods=["GET"])
    app.add_url_rule("/api/slices/<slice>/summary", "sliced_summary", summary,
                     methods=["GET"])
    app.add_url_rule("/api/slices/<slice>/file", "sliced_file", file, methods=["GET"])


@dataclass
class Reckoned:
    """What the front server reckons of a slice job: the report pages see, and the `stored`
    record when that report is its `done` one."""

    user_key: str
    group: str
    job: str
    report: dict
    record: dict | None = None

    @property
    def expired(self):
        error = self.report.get("error")
        return isinstance(error, dict) and error.get("code") == "front.sliced_file_expired"


def reckon(job):
    ctx = context()
    identity = signed_in()
    group = current_group(identity)
    user_key = identity.user_id
    if not _ID.fullmatch(job):
        raise _unknown(ctx, user_key, group, job, "an id of another form")
    now = ctx["clock"].now()
    bucket = ctx["state_bucket"]
    try:
        record = sliced.read(bucket, user_key, job, ctx["log"])
        state = record.get("state") if record is not None else None
        if state == "stored":
            why = "due" if sliced.due(record, now) else \
                None if sliced.file_present(bucket, user_key, job) else "gone"
            if why is None:
                return Reckoned(user_key, group, job, sliced.final_report(record, now), record)
            _expire(ctx, user_key, record, now, why)
            return Reckoned(user_key, group, job, sliced.expired_report(record))
    except BucketUnavailable as exc:
        raise FrontError("front.state_bucket_unreachable", str(exc)) from None
    if state == "expired":
        if now - sliced.moment_of(record["expired_at"]) >= sliced.EXPIRED_RECORD_KEPT_S:
            raise _unknown(ctx, user_key, group, job, "its sliced file expired more than "
                           f"{sliced.EXPIRED_RECORD_KEPT_S} s ago")
        return Reckoned(user_key, group, job, sliced.expired_report(record))
    if state == "failed":
        return Reckoned(user_key, group, job, record["report"])
    report = _ask_slice_service(ctx, user_key, group, job)
    follower = ctx["follower"]
    seen = follower.as_pages_see(user_key, job, report)
    if seen.get("state") not in FINAL_STATES:
        follower.follow(user_key, job, (record or {}).get("group") or group)
    return Reckoned(user_key, group, job, seen)


def _ask_slice_service(ctx, user_key, group, job):
    path = f"/slices/{job}"
    try:
        raw = ctx["slice"].send("GET", path, headers=user_key_header(user_key))
    except SliceUnreachable as exc:
        raise FrontError("front.slice_unreachable", str(exc)) from None
    if raw.status != 200:
        report = slice_report(raw.body)
        if report is not None and report["code"] == "slice.unknown_job":
            whose = ctx["follower"].whose(job)
            raise _unknown(ctx, user_key, group, job,
                           "another user's slice job" if whose not in (None, user_key)
                           else "no slice job of this id for this user key: never one, "
                                "forgotten, or another user's")
        raise refusal(raw, f"GET {path}")
    report = json_object(raw.body)
    if report is None or not isinstance(report.get("state"), str) \
            or not isinstance(report.get("sequence"), int):
        raise RuntimeError(f"GET {path}: the slice service's 200 is not a progress report: "
                           f"{raw.body[:200]!r}")
    return report


def _unknown(ctx, user_key, group, job, why):
    ctx["log"].write("refused", reason="slice_unknown", why=why, user_key=user_key,
                     group=group, slice=job[:64], method=request.method,
                     path=request.path[:200])
    return FrontError("front.slice_unknown", f"slice {job[:64]!r}: {why}")


def _expire(ctx, user_key, record, now, why):
    try:
        sliced.expire(ctx["state_bucket"], user_key, record, now, ctx["log"], by="request",
                      why=why)
    except BucketUnavailable as exc:
        ctx["log"].write("sliced_file_expire_failed", user_key=user_key,
                         group=record.get("group"), slice=record["slice"], why=str(exc))


def _stored_or_refused(reckoned):
    """The `stored` record of a slice job whose sliced file can be had, or the refusal."""
    if reckoned.record is not None:
        return reckoned.record
    if reckoned.expired:
        raise FrontError("front.sliced_file_expired", f"slice {reckoned.job}: expired")
    raise FrontError("front.sliced_file_not_ready",
                     f"slice {reckoned.job}: {reckoned.report.get('state')}, no sliced file "
                     "stored")


# The requests.

@acts_for_group
def ask(slice):  # noqa: A002 - the contract's name for the path's part
    """`GET /api/slices/<slice>`: `{"progress": <the latest report>}`."""
    return {"progress": reckon(slice).report}


@acts_for_group
def summary(slice):  # noqa: A002
    """`GET /api/slices/<slice>/summary`: `{"sliced_file": <its details>}`."""
    reckoned = reckon(slice)
    _stored_or_refused(reckoned)
    return {"sliced_file": reckoned.report["sliced_file"]}


@acts_for_group
def file(slice):  # noqa: A002
    """`GET /api/slices/<slice>/file`: the state bucket's copy, passed through in pieces."""
    ctx = context()
    reckoned = reckon(slice)
    record = _stored_or_refused(reckoned)
    name = sliced.file_name(reckoned.user_key, reckoned.job)
    try:
        stored = ctx["state_bucket"].open(name)
    except NotFound:
        _expire(ctx, reckoned.user_key, record, ctx["clock"].now(), "gone")
        raise FrontError("front.sliced_file_expired",
                         f"slice {reckoned.job}: its sliced file is gone") from None
    except BucketUnavailable as exc:
        raise FrontError("front.state_bucket_unreachable", str(exc)) from None
    offered = record["file"] if _SAFE_NAME.fullmatch(record.get("file") or "") \
        else f"{reckoned.job}.gcode.3mf"
    sent = [0]

    def pieces():
        for piece in stored.chunks():
            sent[0] += len(piece)
            yield piece

    def done():
        stored.close()
        ctx["log"].write("sliced_file_served", user_key=reckoned.user_key,
                         group=reckoned.group, slice=reckoned.job, size_bytes=stored.size,
                         sent_bytes=sent[0], whole=sent[0] == stored.size)

    response = Response(pieces(), 200, content_type="application/octet-stream",
                        headers={"Content-Length": str(stored.size),
                                 "Content-Disposition": f'attachment; filename="{offered}"'})
    response.call_on_close(done)
    return response
