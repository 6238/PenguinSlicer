"""Progress streams, `GET /api/slices/<slice>/events` (README-details.md, "Progress
streams"; contracts/wizard-front-server.md, "Progress streams"), on a fake clock.

A page reads its stream on a thread of its own (`Reader`), as a browser would, so that the
test can move the clock and the stand-in's events while the stream waits. A page that goes
away is a reader that closes its answer, which is what the web server does when a write to
a closed connection fails."""

import json
import threading

import pytest

from front_fakes import BACKSTOP_S, Announcer, FakeClock
from penguin_front import streams as streaming
from sliced_helpers import (DONE, ENDED, GROUP, JOB, OTHER, SLICE_EVENTS, USER, Told,  # noqa: F401
                            app, at, bucket, client, context, done, get, log, queued,
                            requests_to, running, write_stored)


class Recording(FakeClock):
    """The fake clock, noting the seconds of every wait it is asked for."""

    def __init__(self):
        super().__init__()
        self.waits = []

    def sleep(self, seconds, stop=None):
        with self._cond:
            self.waits.append(seconds)
        return super().sleep(seconds, stop)


@pytest.fixture
def clock():
    return Recording()


class Reader:
    """A page reading one progress stream on a thread of its own: the text so far, and
    whether the stream has ended. With `close_after`, the page goes away once it has read
    that many events."""

    def __init__(self, answer, close_after=None):
        self.answer = answer
        self.text = ""
        self.ended = False
        self.told = Announcer()
        self._close_after = close_after
        self._thread = threading.Thread(target=self._read, daemon=True)
        self._thread.start()

    def _read(self):
        try:
            for piece in self.answer.response:
                self.text += piece.decode()
                self.told.announce()
                if self._close_after is not None and len(self.events()) >= self._close_after:
                    break
        finally:
            self.answer.close()
            self.ended = True
            self.told.announce()

    def events(self):
        """The events read so far, each as (kind, id, data) or ("comment", None, text)."""
        found = []
        for block in self.text.split("\n\n")[:-1]:
            if block.startswith(":"):
                found.append(("comment", None, block))
                continue
            fields = dict(line.split(": ", 1) for line in block.split("\n"))
            found.append((fields["event"], fields.get("id"), json.loads(fields["data"])))
        return found

    def progress(self):
        return [data for kind, _id, data in self.events() if kind == "progress"]

    def wait(self, predicate, what):
        try:
            self.told.wait_for(lambda: predicate(self), what)
        except AssertionError as exc:
            raise AssertionError(f"{exc}; the stream so far: {self.text!r}") from None

    def wait_for_end(self):
        self.wait(lambda r: r.ended, "the stream's end")
        self._thread.join(BACKSTOP_S)


def open_stream(client, job=JOB, close_after=None):
    answer = get(client, f"/api/slices/{job}/events", buffered=False)
    assert answer.status_code == 200, answer.get_data(as_text=True)
    return Reader(answer, close_after)


def refused(client, job):
    answer = get(client, f"/api/slices/{job}/events", buffered=False)
    body = answer.get_json()
    answer.close()
    return answer.status_code, body["code"], answer.headers["Content-Type"]


def running_job(standin, job, sequence=5, user=USER):
    standin.add_job(job, user, "p", "s", running(job, sequence), file=b"sliced")


def following_open(standin, job):
    """Wait until the front server's own stream on `job` is open, so that every report the
    stand-in sends from now on reaches it (one opened later starts from the latest)."""
    standin.changes.wait_for(lambda: standin.open_streams(job) == 1,
                             f"the following's stream on {job}")


def streams(app):
    return context(app)["streams"]


# The first events.

def test_the_first_event_is_the_version_and_the_second_the_latest_report(client, standin):
    running_job(standin, "j1", 5)
    reader = open_stream(client, "j1")
    reader.wait(lambda r: len(r.events()) >= 2, "two events")
    kind, _id, data = reader.events()[0]
    assert (kind, data) == ("version", {"version": "20261127T221405Z-ab12cd3"})
    assert reader.events()[1] == ("progress", "5", running("j1", 5))
    assert reader.answer.headers["Content-Type"] == "text/event-stream"
    assert reader.answer.headers["Cache-Control"] == "no-store"
    assert reader.answer.headers["X-PenguinSlicer-Version"] == "20261127T221405Z-ab12cd3"


def test_a_stream_opened_after_reports_gets_the_latest_as_its_second_event(app, client,
                                                                          standin):
    running_job(standin, "j1", 1)
    first = open_stream(client, "j1")
    first.wait(lambda r: len(r.progress()) == 1, "the first stream's report")
    following_open(standin, "j1")
    for sequence in (2, 3, 4):
        standin.report("j1", running("j1", sequence))
    first.wait(lambda r: len(r.progress()) == 4, "the first stream's three new reports")
    second = open_stream(client, "j1")
    second.wait(lambda r: len(r.events()) >= 2, "the second stream's events")
    assert second.events()[1] == ("progress", "4", running("j1", 4))


def test_each_new_report_follows_once_and_a_repeat_is_not_sent_again(client, standin):
    running_job(standin, "j1", 1)
    reader = open_stream(client, "j1")
    reader.wait(lambda r: len(r.progress()) == 1, "the first report")
    following_open(standin, "j1")
    standin.report("j1", running("j1", 2))
    standin.repeat("j1")
    standin.report("j1", running("j1", 3, stage="exporting"))
    reader.wait(lambda r: len(r.progress()) == 3, "two new reports")
    assert [p["sequence"] for p in reader.progress()] == [1, 2, 3]


# Keep-alive.

def test_a_stream_with_nothing_to_report_sends_a_comment_line_every_fifteen_seconds(
        client, standin, clock):
    running_job(standin, "j1")
    reader = open_stream(client, "j1")
    reader.wait(lambda r: len(r.events()) == 2, "two events")
    clock.wait_for_sleepers(1)
    assert clock.waits[-1] == streaming.PROGRESS_KEEPALIVE_S == 15
    clock.advance(14)
    clock.advance(1)
    reader.wait(lambda r: len(r.events()) == 3, "a comment line")
    assert reader.events()[2] == ("comment", None, ": keep-alive")
    assert reader.text.endswith("\n\n: keep-alive\n\n")


def test_the_keep_alive_is_the_contracts_comment_line():
    assert streaming.KEEPALIVE == b": keep-alive\n\n"
    assert ": keep-alive\n\n" in SLICE_EVENTS


# The end of a stream.

def test_a_stream_closes_after_done_which_carries_the_sliced_file_once_stored(
        client, standin, clock):
    running_job(standin, "j1", 2)
    reader = open_stream(client, "j1")
    reader.wait(lambda r: len(r.progress()) == 1, "the first report")
    standin.report("j1", done("j1", 3))
    reader.wait_for_end()
    last = reader.progress()[-1]
    assert last["state"] == "done" and last["sliced_file"]["size_bytes"] == len(b"sliced")
    assert requests_to(standin, "DELETE", "/slices/j1/file")
    assert [p["state"] for p in reader.progress()] == ["running", "done"]


@pytest.mark.parametrize("final", [
    dict(running("j1", 3), state="failed", error={"code": "slice.orca_failed", "message": "m",
                                                  "remedy": "r", "retryable": False,
                                                  "detail": "d"}),
    dict(running("j1", 3), state="cancelled", cancel_reason="replaced"),
])
def test_a_stream_closes_after_failed_or_cancelled(client, standin, final):
    running_job(standin, "j1", 2)
    reader = open_stream(client, "j1")
    reader.wait(lambda r: len(r.progress()) == 1, "the first report")
    standin.report("j1", final)
    reader.wait_for_end()
    assert reader.progress()[-1] == final


def test_a_stored_slice_job_streams_the_contracts_version_and_done_events_then_closes(
        app, client, bucket, clock):
    write_stored(bucket)
    at(clock, ENDED + 6)
    reader = open_stream(client)
    reader.wait_for_end()
    blocks = SLICE_EVENTS.split("\n\n")
    got = reader.text.split("\n\n")
    assert len(got) == 3 and got[2] == "" and got[0] == blocks[0]
    # The event's lines as the example's, its data the same report: the order of the
    # report's fields is the slice service's, which the examples do not hold to one order.
    head, data = got[1].rsplit("\n", 1)
    example_head, example_data = blocks[3].rsplit("\n", 1)
    assert head == example_head == "event: progress\nid: 41"
    assert json.loads(data.removeprefix("data: ")) == \
        json.loads(example_data.removeprefix("data: "))
    assert streams(app).count() == 0


def test_a_running_report_is_written_as_the_contracts_event():
    report = json.loads(SLICE_EVENTS.split("\n\n")[1].split("data: ", 1)[1])
    assert streaming.event("progress", report, report["sequence"]).decode() == \
        SLICE_EVENTS.split("\n\n")[1] + "\n\n"


def test_a_following_that_ends_without_a_final_report_closes_the_stream(client, standin,
                                                                       clock):
    running_job(standin, "j1", 2)
    reader = open_stream(client, "j1")
    reader.wait(lambda r: len(r.progress()) == 1, "the first report")
    following_open(standin, "j1")
    standin.restart()  # the slice service forgets the slice job: its stream closes
    clock.wait_for_sleepers(2)  # the following's wait to reopen, and the page's keep-alive
    clock.advance(1)
    reader.wait_for_end()
    assert [p["state"] for p in reader.progress()] == ["running"]


# Four at most for one user.

def test_a_fifth_stream_of_one_user_is_refused_before_it_starts(app, client, standin, log):
    readers = []
    for n in range(4):
        running_job(standin, f"j{n}")
        readers.append(open_stream(client, f"j{n}"))
    running_job(standin, "j4")
    assert refused(client, "j4") == (429, "front.too_many_streams", "application/json")
    assert streams(app).held(USER) == 4
    assert log.events("error")[-1]["code"] == "front.too_many_streams"


def test_when_one_of_four_closes_a_new_stream_is_accepted(app, client, standin):
    for n in range(3):
        running_job(standin, f"j{n}")
        open_stream(client, f"j{n}")
    running_job(standin, "j3")
    leaving = open_stream(client, "j3", close_after=2)
    leaving.wait_for_end()
    running_job(standin, "j4")
    reader = open_stream(client, "j4")
    reader.wait(lambda r: len(r.events()) == 2, "the new stream's events")
    assert streams(app).held(USER) == 4


def test_at_the_limit_a_new_stream_on_a_job_closes_the_users_oldest_on_that_job(
        app, client, standin, log):
    running_job(standin, "j0")
    oldest = open_stream(client, "j0")
    oldest.wait(lambda r: len(r.events()) == 2, "the oldest stream's events")
    newer = open_stream(client, "j0")
    for n in (1, 2):
        running_job(standin, f"j{n}")
        open_stream(client, f"j{n}")
    reconnected = open_stream(client, "j0")
    oldest.wait_for_end()
    reconnected.wait(lambda r: len(r.events()) == 2, "the reconnected stream's events")
    assert not newer.ended
    assert streams(app).held(USER) == 4
    closed = [line for line in log.events("stream_closed") if line["why"] == "replaced"]
    assert len(closed) == 1 and closed[0]["slice"] == "j0"


def test_below_the_limit_several_streams_on_one_job_stay_open(app, client, standin):
    running_job(standin, "j1")
    readers = [open_stream(client, "j1") for _ in range(3)]
    for reader in readers:
        reader.wait(lambda r: len(r.events()) == 2, "each stream's events")
    standin.report("j1", running("j1", 6))
    for reader in readers:
        reader.wait(lambda r: len(r.progress()) == 2, "each stream's new report")
    assert not any(reader.ended for reader in readers)
    assert standin.open_streams("j1") == 1  # three pages, one connection to the slice service


def test_another_users_count_is_its_own(app, client, standin):
    for n in range(4):
        running_job(standin, f"j{n}")
        open_stream(client, f"j{n}")
    other = streams(app).open(OTHER, "k1")
    assert other is not None and streams(app).held(OTHER) == 1


def test_a_stream_whose_writer_fails_is_removed_from_the_users_count(app, client, standin,
                                                                    log):
    running_job(standin, "j1")
    reader = open_stream(client, "j1", close_after=2)
    reader.wait_for_end()
    assert streams(app).held(USER) == 0 and streams(app).count() == 0
    [line] = log.events("stream_closed")
    assert line["why"] == "page_gone" and line["user_key"] == USER and line["slice"] == "j1"


def test_a_stream_on_a_finished_slice_job_is_not_counted_against_the_four(app, client,
                                                                         standin, bucket):
    for n in range(4):
        running_job(standin, f"j{n}")
        open_stream(client, f"j{n}")
    write_stored(bucket)
    reader = open_stream(client)
    reader.wait_for_end()
    assert reader.progress()[-1]["state"] == "done"


# Refused before the stream starts.

def test_a_stream_on_another_users_slice_job_is_unknown(client, standin):
    running_job(standin, "j1", user=OTHER)
    assert refused(client, "j1") == (404, "front.slice_unknown", "application/json")


def test_a_stream_needs_a_sign_in_and_the_current_group(app, standin):
    client = app.test_client()
    assert client.get(f"/api/slices/{JOB}/events").status_code == 401
    client.get("/signin")
    assert client.get(f"/api/slices/{JOB}/events").status_code == 403


def test_a_head_of_a_stream_holds_nothing(app, client, standin):
    running_job(standin, "j1")
    answer = client.head("/api/slices/j1/events", headers={"X-PenguinSlicer-Group": GROUP})
    assert answer.status_code == 200
    assert answer.headers["Content-Type"] == "text/event-stream"
    assert streams(app).count() == 0


# The lines, and stopping.

def test_opening_and_closing_a_stream_write_their_lines(client, standin, log):
    running_job(standin, "j1", 2)
    reader = open_stream(client, "j1")
    reader.wait(lambda r: len(r.progress()) == 1, "the first report")
    standin.report("j1", dict(running("j1", 3), state="cancelled", cancel_reason="replaced"))
    reader.wait_for_end()
    [opened] = log.events("stream_opened")
    assert opened == {"event": "stream_opened", "user_key": USER, "group": GROUP,
                      "slice": "j1", "streams_held": 1}
    [closed] = log.events("stream_closed")
    assert closed["why"] == "final" and closed["slice"] == "j1" and closed["group"] == GROUP
    assert closed["open_s"] == 0


def test_stopping_ends_every_stream(app, client, standin, log):
    for n in range(2):
        running_job(standin, f"j{n}")
    readers = [open_stream(client, f"j{n}") for n in range(2)]
    for reader in readers:
        reader.wait(lambda r: len(r.events()) == 2, "each stream's events")
    streams(app).stop()
    for reader in readers:
        reader.wait_for_end()
    assert {line["why"] for line in log.events("stream_closed")} == {"stopping"}
    assert streams(app).open(USER, "j9") is None


def test_a_subscription_refused_because_the_following_ended_sends_the_report_and_closes(
        app, client, standin, monkeypatch):
    running_job(standin, "j1")
    monkeypatch.setattr(context(app)["follower"], "subscribe", lambda *_args: None)
    reader = open_stream(client, "j1")
    reader.wait_for_end()
    assert reader.progress() == [running("j1", 5)]
    assert streams(app).count() == 0
