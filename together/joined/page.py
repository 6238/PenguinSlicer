"""The page: the front server's routes driven over HTTP as the wizard drives them
(contracts/wizard-front-server.md), with no browser.

It signs in by the trip (`GET /signin`, the development identity), keeps the cookie as a
browser does, and sends on each request what the wizard sends: the current group in
`X-PenguinSlicer-Group`, its own version in `X-PenguinSlicer-Page`, and the wizard's mark
`X-PenguinSlicer-Wizard: 1` on every changing request. It acts on nothing by itself: each
test says what the wizard would do next, so that the test reads as the wizard's guide does.
"""

import hashlib
import json
import threading
import uuid
from datetime import datetime, timezone

import httpx

from .waits import BACKSTOP_S, Backstop

GROUP = "dev-group"
FINAL_STATES = ("done", "failed", "cancelled")


class Refused(Exception):
    """An answer that is an error report: its status, report and exact bytes."""

    def __init__(self, status, report, body):
        super().__init__(f"{status} {report.get('code') if isinstance(report, dict) else report}")
        self.status = status
        self.report = report
        self.body = body


class Page:
    def __init__(self, front, group=GROUP):
        self.front = front
        self.group = group
        self.version = None
        self.client = httpx.Client(base_url=front.url, timeout=BACKSTOP_S, trust_env=False,
                                   follow_redirects=False)

    def close(self):
        self.client.close()

    def _headers(self, changing=False, group=True):
        headers = {}
        if group:
            headers["X-PenguinSlicer-Group"] = self.group
        if self.version:
            headers["X-PenguinSlicer-Page"] = self.version
        if changing:
            headers["X-PenguinSlicer-Wizard"] = "1"
        return headers

    def _answer(self, answer, ok):
        version = answer.headers.get("X-PenguinSlicer-Version")
        if version:
            self.version = version
        if answer.status_code not in ok:
            try:
                report = answer.json()
            except ValueError:
                report = answer.text
            raise Refused(answer.status_code, report, answer.content)
        return answer

    # Signing in and who the user is.

    def sign_in(self):
        """The trip: `GET /signin` sets the development identity's cookie and sends the
        browser back to `return`."""
        answer = self.client.get("/signin", params={"return": "/"})
        assert answer.status_code == 302, answer.text
        assert answer.headers["location"] == "/"
        assert "penguinslicer" in self.client.cookies
        self._answer(answer, (302,))
        return self

    def me(self):
        return self._answer(self.client.get("/api/me", headers=self._headers(group=False)), (200,)).json()

    def configuration(self):
        return self._answer(self.client.get("/api/configuration", headers=self._headers()), (200,)).json()

    def settings_table(self, gzip=True):
        """The table of settings, and the answer's headers: compressed on the wire when
        `gzip` (httpx undoes it), plain otherwise."""
        headers = {**self._headers(group=False), "Accept-Encoding": "gzip" if gzip else "identity"}
        answer = self._answer(self.client.get("/api/settings-table", headers=headers), (200,))
        return answer.json(), answer.headers

    # Parts and slices.

    def upload(self, path, units="mm"):
        """`POST /api/parts?units=`: the part's bytes exactly as read; gives its record."""
        body = path.read_bytes()
        answer = self.client.post("/api/parts", params={"units": units}, content=body, headers={
            **self._headers(changing=True), "Content-Type": "application/octet-stream"})
        record = self._answer(answer, (201,)).json()
        assert record["sha256"] == hashlib.sha256(body).hexdigest()
        return record

    def submit(self, plate):
        """`POST /api/slices`: gives the slice job of the `202`."""
        answer = self.client.post("/api/slices", content=json.dumps(plate).encode(), headers={
            **self._headers(changing=True), "Content-Type": "application/json"})
        return self._answer(answer, (202,)).json()["slice"]

    def submit_raw(self, plate):
        """`POST /api/slices`, the answer whatever it is."""
        return self.client.post("/api/slices", content=json.dumps(plate).encode(), headers={
            **self._headers(changing=True), "Content-Type": "application/json"})

    def ask(self, slice_id):
        """`GET /api/slices/<slice>`: the latest report as the front server reckons it."""
        return self._answer(self.client.get(f"/api/slices/{slice_id}", headers=self._headers()),
                            (200,)).json()["progress"]

    def summary(self, slice_id):
        return self._answer(self.client.get(f"/api/slices/{slice_id}/summary",
                                            headers=self._headers()), (200,)).json()["sliced_file"]

    def download(self, slice_id, by_link=False):
        """`GET /api/slices/<slice>/file`, with the group in the header or, as Download's plain
        link, in the query; gives (bytes, headers)."""
        if by_link:
            answer = self.client.get(f"/api/slices/{slice_id}/file", params={"group": self.group})
        else:
            answer = self.client.get(f"/api/slices/{slice_id}/file", headers=self._headers())
        answer = self._answer(answer, (200,))
        return answer.content, answer.headers

    def stream(self, slice_id):
        """The slice job's progress stream, opened now: a `Stream` that reads it on a thread
        of its own, so a test can wait for a report while doing something else."""
        return Stream(self, slice_id)

    def follow(self, slice_id):
        """Follow the progress stream to its end; gives every progress report it carried."""
        stream = self.stream(slice_id)
        stream.wait_closed()
        return stream.reports


class Stream:
    """One progress stream of the front server's, read as server-sent events. The events
    arrive in `events` ((name, data) pairs) and the progress reports in `reports`; each wakes
    every waiter."""

    def __init__(self, page, slice_id):
        self.slice_id = slice_id
        self.events = []
        self.reports = []
        #: How many comment lines (`:`, the keep-alive) the stream has carried.
        self.comments = 0
        self.status = None
        self.refusal = None
        self.closed = False
        self.failure = None
        self._changed = threading.Condition()
        self._client = httpx.Client(base_url=page.front.url, trust_env=False,
                                    cookies=page.client.cookies,
                                    timeout=httpx.Timeout(BACKSTOP_S))
        self._headers = page._headers()
        self._thread = threading.Thread(target=self._read, daemon=True, name=f"stream-{slice_id}")
        self._thread.start()

    def _read(self):
        try:
            with self._client.stream("GET", f"/api/slices/{self.slice_id}/events",
                                     headers=self._headers) as answer:
                with self._changed:
                    self.status = answer.status_code
                    self._changed.notify_all()
                if answer.status_code != 200:
                    answer.read()
                    with self._changed:
                        self.refusal = answer.json()
                    return
                name, data = "message", []
                for line in answer.iter_lines():
                    if line == "":
                        if data:
                            self._event(name, "\n".join(data))
                        name, data = "message", []
                    elif line.startswith(":"):
                        with self._changed:
                            self.comments += 1
                            self._changed.notify_all()
                    else:
                        field, _, value = line.partition(":")
                        value = value[1:] if value.startswith(" ") else value
                        if field == "event":
                            name = value
                        elif field == "data":
                            data.append(value)
        except Exception as exc:  # noqa: BLE001 - kept for the test to see
            with self._changed:
                self.failure = exc
        finally:
            self._client.close()
            with self._changed:
                self.closed = True
                self._changed.notify_all()

    def _event(self, name, data):
        value = json.loads(data)
        with self._changed:
            self.events.append((name, value))
            if name == "progress":
                self.reports.append(value)
            self._changed.notify_all()

    def wait_for(self, test, what, backstop_s=BACKSTOP_S):
        """The first progress report for which `test(report)` is true."""
        stop = Backstop(backstop_s, f"the stream of {self.slice_id}: {what}")
        with self._changed:
            seen = 0
            while True:
                for report in self.reports[seen:]:
                    seen += 1
                    if test(report):
                        return report
                if self.closed:
                    stop.fail(f"it closed first ({self.failure or self.refusal or 'no failure'})",
                              self.reports[-5:])
                if not self._changed.wait(stop.left()):
                    stop.fail("not seen", self.reports[-5:])

    def wait_for_comment(self, backstop_s=BACKSTOP_S):
        """The next comment line: what the front server sends while there is nothing to report."""
        stop = Backstop(backstop_s, f"a comment line on the stream of {self.slice_id}")
        with self._changed:
            seen = self.comments
            while self.comments == seen:
                if self.closed:
                    stop.fail("it closed first", self.reports[-5:])
                if not self._changed.wait(stop.left()):
                    stop.fail("not seen", self.reports[-5:])

    def wait_for_stage(self, stage):
        return self.wait_for(lambda r: r.get("stage") == stage, f"the stage {stage!r}")

    def wait_closed(self, backstop_s=BACKSTOP_S):
        stop = Backstop(backstop_s, f"the end of the stream of {self.slice_id}")
        with self._changed:
            while not self.closed:
                if not self._changed.wait(stop.left()):
                    stop.fail("still open", self.reports[-5:])
        if self.failure is not None:
            raise self.failure
        return self

    @property
    def final(self):
        """The final report the stream ended with, or None."""
        last = self.reports[-1] if self.reports else None
        return last if last is not None and last.get("state") in FINAL_STATES else None


def new_id():
    """A plate's id or a submission's value, as the page makes them: a random UUID."""
    return str(uuid.uuid4())


def local_time():
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
