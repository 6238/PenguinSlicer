"""The stand-in for the slice service: its HTTP interface as
contracts/slice-http-interface.md fixes it, served on the loopback address at a port the
system chooses, with every event in the order a test puts it.

Nothing happens by itself. A slice job moves only when the test calls `report`; the
15-second repeat of a quiet stream happens when the test calls `repeat`; a stream closes
early when the test calls `close_streams`. The stand-in records every request it receives
(`requests`) and announces each change on `changes`, so a test waits for a state by being
told, never by looking again after a pause.

Its own sentences (for the refusals the contract gives no example of) are the stand-in's,
not the slice service's; where the contract has an example, the answer is the example.
"""

import gzip
import json
import secrets
import struct
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, Response, request
from werkzeug.exceptions import HTTPException

from front_fakes import Announcer, FakeClock, LoopbackServer

EXAMPLES = Path(__file__).resolve().parents[2] / "contracts" / "examples"

MAX_PART_BYTES = 7_500_084
MAX_PLATE_CONFIGURATION_BYTES = 1_048_576
FINAL_STATES = ("done", "failed", "cancelled")
ID_CHARACTERS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
INCH_MM = 25.4


def example(name):
    return json.loads((EXAMPLES / name).read_text())


def _is_id(value):
    return isinstance(value, str) and 1 <= len(value) <= 64 and set(value) <= ID_CHARACTERS


def _utc(moment, milliseconds=False):
    stamp = datetime.fromtimestamp(moment, timezone.utc)
    if milliseconds:
        return stamp.strftime("%Y-%m-%dT%H:%M:%S.") + f"{stamp.microsecond // 1000:03d}Z"
    return stamp.strftime("%Y-%m-%dT%H:%M:%SZ")


class Refusal(Exception):
    def __init__(self, status, report):
        super().__init__(report["code"])
        self.status = status
        self.report = report


def _report(code, message, remedy, detail, retryable=False, stage="checking", **extra):
    return dict({"code": code, "message": message, "where": {"stage": stage},
                 "remedy": remedy, "retryable": retryable, "detail": detail}, **extra)


def _unknown(job):
    return Refusal(404, _report("slice.unknown_job", "The slicer does not know this slice.",
                                "Slice the plate again.", f"no slice job {job} for this user key"))


@dataclass
class RecordedRequest:
    method: str
    path: str
    query: str
    headers: dict
    body: bytes

    @property
    def user_key(self):
        return self.headers.get("x-penguin-user-key")


@dataclass
class Job:
    job: str
    user_key: str
    plate_id: str
    submission_id: str
    progress: dict
    ended_at: str | None = None
    file: bytes | None = None
    summary: dict | None = None
    part_warnings: list = field(default_factory=list)
    #: What the open streams have been sent since they opened: ("report" | "repeat", report)
    #: or ("close", None).
    emissions: list = field(default_factory=list)
    streams: int = 0
    #: A test's fault for the sliced file: cut the connection after this many bytes.
    cut_after: int | None = None
    #: False: send the sliced file without a Content-Length, so only a count gives its size.
    send_length: bool = True

    @property
    def ended(self):
        return self.progress.get("state") in FINAL_STATES

    def entry(self):
        return {"job": self.job, "user_key": self.user_key, "plate_id": self.plate_id,
                "submission_id": self.submission_id, "progress": self.progress,
                "file_on_disk": self.file is not None and self.progress.get("state") == "done",
                "ended_at": self.ended_at}


class SliceStandIn:
    def __init__(self, clock=None):
        self.clock = clock or FakeClock()
        self.changes = Announcer()
        self.requests = []
        self.refusals = 0
        self.next_job_ids = []
        self.expected_s = 75
        self.stopping = False
        self.log_capacity = 10_000
        self.log_page = 1_000
        self.settings_table = (EXAMPLES / "settings-table.json").read_bytes()
        self._lock = threading.RLock()
        self._next_answers = []
        self._generation = 0
        self._reset_process()
        self.app = self._make_app()
        self._server = LoopbackServer(self.app)

    # The process.

    def _reset_process(self):
        self.process = "p" + secrets.token_hex(4)
        self.jobs = {}
        self.parts = {}
        self._log_lines = []
        self._log_count = 0

    def restart(self):
        """A restarted slice service process: it knows none of the earlier one's slice jobs,
        parts or log lines, and its log numbering begins again at 1."""
        with self._lock:
            self._reset_process()
            self._generation += 1
        self.changes.announce()

    def start(self):
        return self._server.start()

    @property
    def url(self):
        return self._server.url

    def stop(self):
        with self._lock:
            self._generation += 1
        self.changes.announce()
        self._server.stop()

    def unreachable(self):
        """Stop listening: every connection is refused until `reachable`."""
        self.stop()

    def reachable(self):
        self.start()

    # The test's controls.

    def answer_next(self, method, path, status, body):
        """The next request of `method` and `path` is answered so, once."""
        with self._lock:
            self._next_answers.append((method, path, status, body))

    def add_job(self, job, user_key, plate_id, submission_id, progress, *, file=None,
                summary=None, ended_at=None):
        with self._lock:
            self.jobs[job] = Job(job, user_key, plate_id, submission_id, dict(progress),
                                 ended_at=ended_at, file=file,
                                 summary=summary if summary is not None
                                 else example("sliced-file.json"))
        self.changes.announce()
        return self.jobs[job]

    def report(self, job, progress):
        """The slice job's next progress report, sent to every open stream; a final one
        notes when the slice job ended and closes the streams."""
        with self._lock:
            record = self.jobs[job]
            record.progress = dict(progress)
            if record.ended and record.ended_at is None:
                record.ended_at = _utc(self.clock.now())
            record.emissions.append(("report", record.progress))
        self.changes.announce()

    def repeat(self, job):
        """The 15-second repeat of a quiet stream: the latest report, sent again."""
        with self._lock:
            record = self.jobs[job]
            record.emissions.append(("repeat", record.progress))
        self.changes.announce()

    def close_streams(self, job):
        """Close every open stream of the slice job before its final report."""
        with self._lock:
            self.jobs[job].emissions.append(("close", None))
        self.changes.announce()

    def cut_file(self, job, after):
        with self._lock:
            self.jobs[job].cut_after = after

    def open_streams(self, job):
        with self._lock:
            return self.jobs[job].streams

    def cancels(self):
        return [r.path.split("/")[2] for r in self.requests
                if r.method == "DELETE" and r.path.count("/") == 2]

    def log_line(self, event, **fields):
        with self._lock:
            self._log_count += 1
            line = {"n": self._log_count,
                    "time": fields.pop("time", None) or _utc(self.clock.now(), True),
                    "component": "slice", "event": event, **fields}
            self._log_lines.append(line)
            del self._log_lines[:-self.log_capacity]
        self.changes.announce()
        return line

    # The application.

    def _make_app(self):
        app = Flask("slice_standin", static_folder=None)
        app.url_map.strict_slashes = False
        standin = self

        @app.before_request
        def record():
            body = request.get_data(cache=True) if request.content_length is None or \
                request.content_length <= MAX_PLATE_CONFIGURATION_BYTES * 8 else b""
            with standin._lock:
                standin.requests.append(RecordedRequest(
                    request.method, request.path, request.query_string.decode(),
                    {k.lower(): v for k, v in request.headers.items()}, body))
                for n, (method, path, status, answer) in enumerate(standin._next_answers):
                    if method == request.method and path == request.path:
                        del standin._next_answers[n]
                        standin.changes.announce()
                        return Response(json.dumps(answer), status,
                                        mimetype="application/json")
            standin.changes.announce()
            return None

        @app.after_request
        def no_store(response):
            response.headers["Cache-Control"] = "no-store"
            return response

        @app.errorhandler(Refusal)
        def refused(refusal):
            return Response(json.dumps(refusal.report), refusal.status,
                            mimetype="application/json")

        @app.errorhandler(HTTPException)
        def not_offered(exc):
            what = "a path the interface does not offer" if exc.code == 404 \
                else "a method this path does not take"
            return Response(json.dumps(_report(
                "slice.bad_request", "The slicer was sent a request it does not take.",
                "Try again; if it happens again, the server needs fixing.",
                f"{request.method} {request.path}: {what}")), exc.code,
                mimetype="application/json")

        def user_key():
            key = request.headers.get("X-Penguin-User-Key", "")
            if not key:
                raise Refusal(400, _report(
                    "slice.no_user_key", "The slicer was not told whose request this is.",
                    "Try again; if it happens again, the server needs fixing.",
                    f"{request.method} {request.path} without X-Penguin-User-Key"))
            return key

        def own_job(job):
            key = user_key()
            with standin._lock:
                record = standin.jobs.get(job)
                if record is None:
                    raise _unknown(job)
                if record.user_key != key:
                    standin.refusals += 1
                    raise _unknown(job)
                return record

        app.add_url_rule("/parts", "parts", lambda: standin._upload(user_key()),
                         methods=["POST"])
        app.add_url_rule("/slices", "submit", lambda: standin._submit(user_key()),
                         methods=["POST"])
        app.add_url_rule("/slices", "list", standin._list, methods=["GET"])
        app.add_url_rule("/slices/<job>", "latest", lambda job: own_job(job).progress,
                         methods=["GET"])
        app.add_url_rule("/slices/<job>", "cancel",
                         lambda job: standin._cancel(own_job(job)), methods=["DELETE"])
        app.add_url_rule("/slices/<job>/events", "events",
                         lambda job: standin._events(own_job(job)), methods=["GET"])
        app.add_url_rule("/slices/<job>/file", "file",
                         lambda job: standin._file(own_job(job)), methods=["GET"])
        app.add_url_rule("/slices/<job>/summary", "summary",
                         lambda job: standin._summary(own_job(job)), methods=["GET"])
        app.add_url_rule("/slices/<job>/file", "delete_file",
                         lambda job: standin._delete_file(own_job(job)), methods=["DELETE"])
        app.add_url_rule("/settings-table", "settings_table", standin._settings_table,
                         methods=["GET"])
        app.add_url_rule("/log", "log", standin._log, methods=["GET"])
        return app

    # Parts.

    def _upload(self, key):
        units = request.args.get("units")
        if units not in ("mm", "in"):
            raise Refusal(400, _report(
                "slice.bad_units", "The slicer was not told the part's units.",
                "Choose millimetres or inches for the part and add it again.",
                f"units {units!r}"))
        length = request.content_length
        if length is None:
            raise Refusal(400, _report(
                "slice.bad_request", "The slicer was sent a part without its size.",
                "Try again; if it happens again, the server needs fixing.",
                "upload without Content-Length"))
        if length > MAX_PART_BYTES:
            raise Refusal(413, example("error-report-part-over-size.json")
                          | {"detail": f"upload Content-Length {length:,} bytes, "
                                       f"cap {MAX_PART_BYTES:,}"})
        body = request.get_data()
        record = _measure(body, units)
        with self._lock:
            self.parts.setdefault(key, {})[(record["sha256"], units)] = record
        return record, 201

    # Slice jobs.

    def _submit(self, key):
        length = request.content_length or 0
        if length > MAX_PLATE_CONFIGURATION_BYTES:
            raise Refusal(413, example("error-report-plate-configuration-over-size.json")
                          | {"detail": f"plate configuration Content-Length {length:,} "
                                       f"bytes, cap {MAX_PLATE_CONFIGURATION_BYTES:,}"})
        plate = _plate_configuration(request.get_data())
        with self._lock:
            for record in self.jobs.values():
                if record.user_key == key and record.submission_id == plate["submission_id"]:
                    return self._accepted(record), 202
            if self.stopping:
                raise Refusal(503, example("slice-http/stopping.json"))
            held = self.parts.get(key, {})
            missing = [{"key": k, "sha256": p["sha256"], "units": p["units"]}
                       for k, p in plate["parts"].items()
                       if (p.get("sha256"), p.get("units")) not in held]
            if missing:
                raise Refusal(422, _parts_missing(missing))
            live = [r for r in self.jobs.values() if not r.ended]
            replaced = [r for r in live if r.user_key == key and r.plate_id == plate["plate_id"]]
            if len(live) - len(replaced) >= 3:
                raise Refusal(503, _report(
                    "slice.busy", "The slicer is busy with other plates.",
                    "Slice again in a few minutes.", "one slice running and two waiting",
                    retryable=True, stage="queued"))
            for record in replaced:
                record.progress = dict(record.progress, state="cancelled",
                                       sequence=record.progress.get("sequence", 0) + 1,
                                       cancel_reason="replaced")
                record.ended_at = _utc(self.clock.now())
                record.emissions.append(("report", record.progress))
            job = self.next_job_ids.pop(0) if self.next_job_ids else "j" + secrets.token_hex(8)
            ahead = len(live) - len(replaced)
            record = Job(job, key, plate["plate_id"], plate["submission_id"], {
                "job": job, "state": "queued", "stage": "queued",
                "stage_label": "Waiting for the slicer", "elapsed_s": 0,
                "expected_s": self.expected_s, "sequence": 1, "ahead": ahead})
            self.jobs[job] = record
        self.changes.announce()
        return self._accepted(record), 202

    @staticmethod
    def _accepted(record):
        return {"job": record.job, "plate_id": record.plate_id,
                "submission_id": record.submission_id, "progress": record.progress,
                "part_warnings": record.part_warnings}

    def _list(self):
        with self._lock:
            return {"slices": [record.entry() for record in self.jobs.values()]}

    def _cancel(self, record):
        with self._lock:
            if record.ended:
                return {"job": record.job, "cancel": "finished", "progress": record.progress}
            record.progress = dict(record.progress, state="cancelled",
                                   sequence=record.progress.get("sequence", 0) + 1,
                                   cancel_reason="requested")
            record.ended_at = _utc(self.clock.now())
            record.emissions.append(("report", record.progress))
        self.changes.announce()
        return {"job": record.job, "cancel": "cancelled", "progress": record.progress}

    def _events(self, record):
        with self._lock:
            start = len(record.emissions)
            first = record.progress
            generation = self._generation
            record.streams += 1
        self.changes.announce()

        def event(report):
            return f"id: {report['sequence']}\nevent: progress\ndata: {json.dumps(report)}\n\n"

        def stream():
            try:
                yield event(first)
                if first.get("state") in FINAL_STATES:
                    return
                seen = start
                while True:
                    with self.changes._cond:
                        self.changes._cond.wait_for(
                            lambda: len(record.emissions) > seen
                            or self._generation != generation)
                        if self._generation != generation:
                            return
                        kind, report = record.emissions[seen]
                        seen += 1
                    if kind == "close":
                        return
                    yield event(report)
                    if kind == "report" and report.get("state") in FINAL_STATES:
                        return
            finally:
                with self._lock:
                    record.streams -= 1
                self.changes.announce()

        return Response(stream(), 200, mimetype="text/event-stream")

    # The sliced file.

    def _not_ready(self, record):
        state = record.progress.get("state")
        if state == "failed":
            raise Refusal(409, record.progress.get("error") or _report(
                "slice.orca_failed", "The slice failed.", "Slice again.", "failed"))
        if state == "cancelled":
            raise Refusal(409, _report("slice.cancelled", "This slice was stopped.",
                                       "Slice the plate again.", "cancelled"))
        if state != "done":
            raise Refusal(409, _report("slice.not_ready", "This slice has not finished.",
                                       "Wait for the slice to finish.", f"state {state}"))
        if record.file is None:
            raise Refusal(410, _report("slice.file_gone", "This sliced file is gone.",
                                       "Slice the plate again.", "deleted"))

    def _file(self, record):
        self._not_ready(record)
        body, cut = record.file, record.cut_after

        def pieces():
            if cut is None:
                yield body
                return
            yield body[:cut]
            raise ConnectionAbortedError("the stand-in cut the sliced file on purpose")

        headers = {"Content-Disposition": f'attachment; filename="{record.summary["file"]}"'}
        if record.send_length:
            headers["Content-Length"] = str(len(body))
        return Response(pieces(), 200, headers=headers, mimetype="application/octet-stream")

    def _summary(self, record):
        self._not_ready(record)
        return Response(json.dumps(record.summary), 200, mimetype="application/json")

    def _delete_file(self, record):
        state = record.progress.get("state")
        if state not in FINAL_STATES:
            raise Refusal(409, _report("slice.not_ready", "This slice has not finished.",
                                       "Wait for the slice to finish.", f"state {state}"))
        with self._lock:
            record.file = None
        self.changes.announce()
        return {"job": record.job, "file": "deleted"}

    # The table of settings and the log.

    def _settings_table(self):
        if "gzip" in request.headers.get("Accept-Encoding", ""):
            return Response(gzip.compress(self.settings_table), 200,
                            headers={"Content-Encoding": "gzip"}, mimetype="application/json")
        return Response(self.settings_table, 200, mimetype="application/json")

    def _log(self):
        after = request.args.get("after", "")
        if not after.isascii() or not after.isdigit():
            raise Refusal(400, _report(
                "slice.bad_request", "The slicer was sent a request it does not take.",
                "Try again; if it happens again, the server needs fixing.",
                f"after {after!r} is not a whole number"))
        after = int(after)
        with self._lock:
            lines = [line for line in self._log_lines if line["n"] > after]
            oldest = self._log_lines[0]["n"] if self._log_lines else self._log_count + 1
            dropped = max(0, oldest - after - 1)
            page = lines[:self.log_page]
            return {"process": self.process, "lines": page, "dropped": dropped,
                    "more": len(lines) > len(page)}


def _measure(body, units):
    """The part's record, measured as the slice service measures a binary STL; a body that
    is not one is refused as unreadable."""
    import hashlib

    count = struct.unpack_from("<I", body, 80)[0] if len(body) >= 84 else -1
    if count < 1 or len(body) != 84 + 50 * count:
        raise Refusal(422, _report("slice.part_unreadable", "This part could not be read.",
                                   "Export the part again as a binary STL and add it again.",
                                   f"{len(body)} bytes"))
    scale = INCH_MM if units == "in" else 1.0
    low, high, volume = [float("inf")] * 3, [float("-inf")] * 3, 0.0
    for n in range(count):
        values = struct.unpack_from("<12f", body, 84 + 50 * n)
        a, b, c = values[3:6], values[6:9], values[9:12]
        for vertex in (a, b, c):
            for axis in range(3):
                low[axis] = min(low[axis], vertex[axis])
                high[axis] = max(high[axis], vertex[axis])
        volume += (a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0])
                   + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6
    return {"sha256": hashlib.sha256(body).hexdigest(), "units": units,
            "measurements": {"triangles": count,
                             "size_mm": [round((high[i] - low[i]) * scale, 3) for i in range(3)],
                             "volume_mm3": round(abs(volume) * scale ** 3, 3)},
            "warnings": []}


def _plate_configuration(body):
    def refused(why):
        return Refusal(400, _report(
            "slice.bad_plate_configuration", "This plate configuration could not be read.",
            "Lay out the plate again and send a new slice.", why))

    try:
        plate = json.loads(body)
    except ValueError as exc:
        raise refused(f"not JSON: {exc}") from None
    if not isinstance(plate, dict):
        raise refused("not a JSON object")
    for name in ("plate_id", "submission_id"):
        if not _is_id(plate.get(name)):
            raise refused(f"{name} missing or of a bad form")
    if not isinstance(plate.get("parts"), dict):
        raise refused("parts is not an object")
    return plate


def _parts_missing(missing):
    report = example("error-report-parts-missing.json")
    report["message"] = f"The slicer no longer has {len(missing)} of this plate's parts."
    report["where"]["missing_parts"] = missing
    report["detail"] = "missing from the part store: " + ", ".join(
        f"{m['sha256']} ({m['units']})" for m in missing)
    return report
