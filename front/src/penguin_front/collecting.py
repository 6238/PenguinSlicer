"""Collecting at start (README-details.md, "Starting, and what a restart does"; the guide's
"Why nothing is lost").

When the front server starts it asks the slice service for every slice job it holds
(`GET /slices`), and asks again, after waits growing from `FIRST_WAIT_S` to `LONGEST_WAIT_S`
on the front server's clock, until the slice service answers with the list. It answers
requests meanwhile: the collection runs on a thread of its own. Then, for each slice job:

- **waiting or running:** followed again, with the group its record in the state bucket
  holds (none when it has no record);
- **done, its sliced file still held by the slice service (`file_on_disk`):** collected,
  when the state bucket holds no `stored` or `failed` record for it: followed, and so
  stored as every followed slice job is, with its record's group and with the list's
  `ended_at` as the moment the slice ended, from which the two hours count. When the
  record is `stored` or `failed` already (a front server stopped between writing the record
  and telling the slice service), it is followed too, which fetches nothing and only tells
  the slice service to delete its copy;
- **anything else** (failed, cancelled, a sliced file the slice service no longer holds, a
  record already `expired`): left alone.

A state bucket that does not answer while the records are read makes the whole pass wait
and start again: following a slice job without its group would store it without one.
"""

import re
import threading

from . import sliced
from .buckets import BadName, BucketUnavailable
from .following import FINAL_STATES, FIRST_WAIT_S, LONGEST_WAIT_S  # noqa: F401
from .following import _Waits
from .slice_client import SliceUnreachable, json_object

_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")
_ENDED_AT = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
#: The most of an entry the front server cannot read that its line holds.
_ENTRY_CHARS = 300


class _Again(Exception):
    """The pass is asked again after a wait, for the reason given."""


class Collector:
    def __init__(self, *, clock, slice_client, bucket, follower, log):
        self._clock = clock
        self._slice = slice_client
        self._bucket = bucket
        self._follower = follower
        self._log = log
        self._stopping = threading.Event()
        self._thread = None
        #: Set once the list has been read and every slice job of it handled.
        self.collected = threading.Event()

    def start(self):
        self._thread = threading.Thread(target=self.run, name="collect", daemon=True)
        self._thread.start()

    def stop(self):
        """End the collection at its next wait, and wait for it."""
        self._stopping.set()
        self._clock.wake()
        if self._thread is not None:
            self._thread.join()

    def run(self):
        waits = _Waits()
        while not self._stopping.is_set():
            try:
                self._collect_once()
            except _Again as again:
                wait = waits.take()
                self._log.write("slices_list_retry", why=str(again), wait_s=wait)
                if self._clock.sleep(wait, self._stopping):
                    return
                continue
            self.collected.set()
            return

    def _collect_once(self):
        try:
            raw = self._slice.send("GET", "/slices")
        except SliceUnreachable as exc:
            raise _Again(str(exc)) from None
        if raw.status != 200:
            raise _Again(f"GET /slices answered {raw.status}")
        answer = json_object(raw.body)
        entries = answer.get("slices") if answer is not None else None
        if not isinstance(entries, list):
            raise _Again("GET /slices answered with what is not a list of slice jobs")
        counts = {"listed": len(entries), "followed": 0, "collecting": 0,
                  "already_stored": 0, "left": 0, "unreadable": 0}
        plan = []
        for entry in entries:
            readable = _readable(entry)
            if readable is None:
                counts["unreadable"] += 1
                self._log.write("slices_entry_unreadable", entry=repr(entry)[:_ENTRY_CHARS])
                continue
            user_key, job, state = readable
            kind, record = self._kind(entry, user_key, job, state)
            counts[kind] += 1
            if kind != "left":
                plan.append((kind, user_key, job, record, entry))
        for kind, user_key, job, record, entry in plan:
            group = record.get("group") if record is not None else None
            ended_at = _ended_at(entry) if kind != "followed" else None
            started = self._follower.follow(user_key, job, group, ended_at=ended_at)
            if not started and kind == "followed":
                counts["followed"] -= 1
        self._log.write("slices_collected", **counts)

    def _kind(self, entry, user_key, job, state):
        """What the start does with one slice job, and its record (None when it has
        none)."""
        if state == "done" and entry.get("file_on_disk") is not True:
            return "left", None
        if state in FINAL_STATES and state != "done":
            return "left", None
        try:
            record = sliced.read(self._bucket, user_key, job, self._log)
        except BucketUnavailable as exc:
            raise _Again(f"reading the record of {job}: {exc}") from None
        if state != "done":
            return "followed", record
        found = record.get("state") if record is not None else None
        if found in ("stored", "failed"):
            return "already_stored", record
        if found in (None, "submitted"):
            return "collecting", record
        return "left", record


def _readable(entry):
    """The user key, id and state of a listed slice job, or None for an entry of another
    form."""
    if not isinstance(entry, dict):
        return None
    user_key, job, progress = entry.get("user_key"), entry.get("job"), entry.get("progress")
    if not isinstance(job, str) or not _ID.fullmatch(job) or not isinstance(user_key, str) \
            or not isinstance(progress, dict) or not isinstance(progress.get("state"), str):
        return None
    try:
        sliced.check_user_key(user_key)
    except BadName:
        return None
    return user_key, job, progress["state"]


def _ended_at(entry):
    """The list's `ended_at` when it is of the form RFC 3339 in UTC to the second; else None,
    and the two hours count from when the following hears the slice is done."""
    ended_at = entry.get("ended_at")
    if isinstance(ended_at, str) and _ENDED_AT.fullmatch(ended_at):
        try:
            sliced.moment_of(ended_at)
        except ValueError:
            return None
        return ended_at
    return None
