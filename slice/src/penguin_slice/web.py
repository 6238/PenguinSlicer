"""The slice service's HTTP interface, its one interface: a Flask app factory.

    POST   /slices                a plate configuration (form field `plate_configuration`,
                                  JSON) and its STL files (one file field per part, named as
                                  the part's `stl`): 202 with the first progress report and
                                  the part warnings
    GET    /slices/<job>          the slice job's latest progress report
    GET    /slices/<job>/events   the slice job's progress reports as a stream
                                  (text/event-stream), the latest first, ending with the final one
    DELETE /slices/<job>          cancel the slice job: {"cancel": cancelled|cancelling|finished}
    GET    /slices/<job>/file     the sliced file of a done slice job, and nothing else
    GET    /slices/<job>/summary  the sliced file's summary (contracts/sliced-file.md), as JSON

Every answer that is not a success is an error report (contracts/error-report.md), with
an HTTP status: 400 for a request that is not a plate configuration, 404 for an unknown
slice job or a path not offered, 405 for a method a path does not take, 409 for a sliced
file or summary that is not there (yet), 410 for a sliced file gone from the disk, 413 for
an upload too large, 422 for a plate configuration refused by a check, 500 for the print
server's own failure (its work folder not writable, a bug), 503 when the queue is full.

Each plate configuration is read and checked when it arrives, before a slice job is
queued for it, so a refusal comes back at once. A slice job's files live under
`work_dir/<job>/`: the uploaded parts, the scratch folder of the slice, and the sliced
file, all removed when the slice job ends
without a file or when its record expires. At start the app refuses a bad setting
(limits.SettingError), removes scratch left by a process that died
(service.clean_stale_scratch) and starts the job pool's sweeper.

One app runs in one slice service process, and its slice jobs live in this process's
memory (jobs.JobPool): a client must keep talking to the slice service process that
accepted its slice job, and a server that runs several worker processes behind one
address loses slice jobs.
"""
import json
import re
import shutil
import tempfile
import traceback
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_file
from werkzeug.exceptions import HTTPException

from . import limits
from .errors import error_report, report_for_code
from .jobs import FINAL, JobPool, QueueFull, SafeLog, exception_text
from .service import (BAD_CONFIGURATION_MESSAGE, PlateConfigurationRefused, clean_stale_scratch, make_scratch,
                      read_plate_configuration, slice_plate_configuration)
from .slicer import CANCELLED_MESSAGE, SCRATCH_UNWRITABLE_MESSAGE, SliceError

UPLOAD_NAME_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z')
FORM_FIELD = "plate_configuration"
# What a plate configuration can send: one STL per part it uses, at most MAX_PARTS of them
# (instances of one part share its file), and a megabyte for the form itself.
MAX_UPLOAD_BYTES = limits.MAX_PARTS * limits.MAX_PART_BYTES + 1024 * 1024
UNKNOWN_JOB_MESSAGE = "The print server does not know this slice; it may have expired."
NOT_READY_MESSAGE = "The sliced file is not ready yet."
TOO_LARGE_UPLOAD_MESSAGE = "This plate configuration is too large to receive."
NOT_OFFERED_MESSAGE = "The print server does not offer {method} {path}."
FILE_GONE_MESSAGE = "The sliced file is no longer on the print server."
UPLOADS = "parts"
LOGGED_ENTRIES = 100          # parts and uploads listed in a refusal's log line, at most


def _report(code, message, detail="", status=400):
    return jsonify(report_for_code(code, message, detail)), status


def _status_for(report):
    return 503 if report["code"] == "slice.busy" else 422 if report["where"]["stage"] == "checking" else 500


def _parts_named(data, limit=LOGGED_ENTRIES):
    """The parts a plate configuration names, for the log line of a refusal: {key: {name,
    stl}}, or None when it names none that can be read."""
    parts = data.get("parts") if isinstance(data, dict) else None
    if not isinstance(parts, dict):
        return None
    return {str(key)[:64]: {"name": str(part.get("name"))[:80], "stl": str(part.get("stl"))[:120]}
            if isinstance(part, dict) else {"name": None, "stl": None} for key, part in list(parts.items())[:limit]}


def _upload_sizes(limit=LOGGED_ENTRIES):
    """{field name: bytes} of the request's uploaded files, for the log; None when the
    request's body could not be read."""
    try:
        sizes = {}
        for name, storage in list(request.files.items(multi=True))[:limit]:
            stream = storage.stream
            here = stream.tell()
            stream.seek(0, 2)
            sizes[name[:80]] = stream.tell()
            stream.seek(here)
        return sizes
    except Exception:            # noqa: BLE001 - a body Werkzeug could not parse: nothing to list
        return None


def slice_worker(job_id, configuration, context):
    """The pool's worker: slice a checked PlateConfiguration into its slice job's folder."""
    out = configuration.work_dir / "out"
    sliced = slice_plate_configuration(None, out, configuration=configuration, stop=context.stop,
                                       on_progress=context.progress)
    result = {"path": str(sliced.path), "summary": sliced.summary, "file": sliced.path.name,
              "peak_rss_kb": sliced.peak_rss_kb, "orca_wall_s": sliced.wall_s,
              "work_dir": str(configuration.work_dir)}
    for key in ("memory_note", "stop_note"):
        if getattr(sliced, key):
            result[key] = getattr(sliced, key)
    return result


def remove_job_files(configuration):
    """The pool's cleanup: a slice job's folder (its uploads, its scratch, its sliced file)."""
    if configuration is not None and configuration.work_dir is not None:
        shutil.rmtree(configuration.work_dir, ignore_errors=True)


def create_app(work_dir=None, pool=None, *, log=None, start_sweeper=True, environ=None):
    """The app. `work_dir` holds every slice job's files (a new temporary folder when None);
    `pool` is a JobPool whose worker is slice_worker (made here when None); `log` takes the
    pool's log lines (dicts), through jobs.SafeLog, so a log that fails never changes an
    answer or a slice job: the pool made here counts those failures (JobPool.log_failures).
    Raises limits.SettingError, before anything else, for a setting it refuses."""
    limits.max_peak_mb(environ)          # a bad memory ceiling stops the service at start
    work_dir = Path(work_dir or tempfile.mkdtemp(prefix="penguin-slice-")).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    log = log if isinstance(log, SafeLog) else SafeLog(log or (lambda entry: None))     # a failing sink is counted
    clean_stale_scratch(work_dir)

    pool = pool or JobPool(slice_worker, error_report=error_report, cleanup=remove_job_files, log=log)
    if start_sweeper:
        pool.start_sweeper()
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
    app.extensions["penguin_slice_pool"] = pool

    def submitting():
        return request.method == "POST" and request.path == "/slices"

    def log_refusal(body, status, data=None, extra=None):
        """The log line of a plate configuration refused before any slice job existed for it:
        every refusal at POST /slices, whatever the step that refused it (slice jobs are the
        pool's to log)."""
        log({"event": "slice_job", "job": None, "state": "refused", "http_status": status,
             "error_code": body["code"], "error_detail": body["detail"], "parts": _parts_named(data),
             "uploads": _upload_sizes(), **(extra or {})})

    @app.errorhandler(413)
    def too_large(_error):
        # Raised only while a request body is read, and POST /slices is the one route that reads one.
        body = report_for_code("slice.bad_plate_configuration", TOO_LARGE_UPLOAD_MESSAGE,
                               f"over {MAX_UPLOAD_BYTES:,} bytes")
        log_refusal(body, 413)
        return jsonify(body), 413

    @app.errorhandler(HTTPException)
    def not_offered(error):
        # No such path (404), a method a path does not take (405), and the rest of Flask's own
        # (a request body Werkzeug cannot parse is one: logged when it was a plate configuration).
        body = report_for_code("slice.bad_request", NOT_OFFERED_MESSAGE.format(method=request.method,
                                                                               path=request.path[:80]),
                               f"HTTP {error.code} {error.name}")
        if submitting():
            log_refusal(body, error.code)
        return jsonify(body), error.code

    @app.errorhandler(Exception)
    def unexpected(error):
        body = error_report(error)
        trace = traceback.format_exc()[-2000:]
        if submitting():
            log_refusal(body, 500, extra={"traceback": trace})
        else:
            log({"event": "slice_http_error", "path": request.path[:80], "error": exception_text(error),
                 "error_code": body["code"], "traceback": trace})
        return jsonify(body), 500

    @app.post("/slices")
    def submit():
        data = None
        raw = request.form.get(FORM_FIELD)
        if raw is None:
            problem = f"the request has no {FORM_FIELD} field"
            body, status = report_for_code("slice.bad_plate_configuration",
                                           BAD_CONFIGURATION_MESSAGE.format(problem=problem), problem), 400
        else:
            try:
                data = json.loads(raw)
                body, status = _queue(data)
            except (ValueError, RecursionError) as exc:
                problem = f"its {FORM_FIELD} field is not JSON"
                body, status = report_for_code("slice.bad_plate_configuration",
                                               BAD_CONFIGURATION_MESSAGE.format(problem=problem),
                                               f"{type(exc).__name__}: {exc}"[:300]), 400
        if status != 202:
            log_refusal(body, status, data)
        return jsonify(body), status

    def _queue(data):
        """Save the uploads, check the plate configuration and queue its slice job: (answer, status)."""
        try:
            job_dir = make_scratch(work_dir)
            uploads = job_dir / UPLOADS
            uploads.mkdir()
        except OSError as exc:
            return report_for_code("slice.scratch_unwritable", SCRATCH_UNWRITABLE_MESSAGE,
                                   f"{type(exc).__name__}: {exc}"), 500
        try:
            for field_name, storage in request.files.items(multi=True):
                if not UPLOAD_NAME_RE.fullmatch(field_name):
                    problem = f"an uploaded file is named {field_name[:60]!r}, which is not a plain file name"
                    raise PlateConfigurationRefused(BAD_CONFIGURATION_MESSAGE.format(problem=problem), problem)
                try:
                    storage.save(uploads / field_name)
                except OSError as exc:
                    # A full disk, a work folder gone: the print server's, before any slice.
                    raise SliceError(SCRATCH_UNWRITABLE_MESSAGE, f"saving the upload {field_name!r}: "
                                                                 f"{type(exc).__name__}: {exc}",
                                     error_code="slice.scratch_unwritable") from None
            configuration = read_plate_configuration(data, uploads, confine_to=uploads, environ=environ)
            configuration.work_dir = job_dir
            job_id = pool.submit(configuration, describe=configuration.describe(),
                                 expected_s=configuration.expected_s)
        except Exception as exc:
            shutil.rmtree(job_dir, ignore_errors=True)
            body = error_report(exc)
            if isinstance(exc, QueueFull):
                return body, 503
            return body, _status_for(body) if body["code"] != "slice.bad_plate_configuration" else 400
        return {"job": job_id, "progress": pool.get(job_id), "part_warnings": configuration.part_warnings()}, 202

    def unknown(job_id):
        return _report("slice.unknown_job", UNKNOWN_JOB_MESSAGE, f"job {job_id[:40]!r}", 404)

    def finished(job_id):
        """(the done slice job's result, None), or (None, the error answer): the same for the
        sliced file and its summary."""
        report = pool.get(job_id)
        if report is None:
            return None, unknown(job_id)
        if report["state"] == "failed":
            return None, (jsonify(report["error"]), 409)
        if report["state"] == "cancelled":
            return None, _report("slice.cancelled", CANCELLED_MESSAGE, f"job {job_id}", 409)
        result = pool.result(job_id)
        if report["state"] not in FINAL or result is None:
            return None, _report("slice.not_ready", NOT_READY_MESSAGE, f"job {job_id} is {report['state']}", 409)
        return result, None

    def gone(job_id, exc):
        return _report("slice.file_gone", FILE_GONE_MESSAGE, f"job {job_id}: {type(exc).__name__}: {exc}", 410)

    @app.get("/slices/<job_id>")
    def progress(job_id):
        report = pool.get(job_id)
        return jsonify(report) if report else unknown(job_id)

    @app.get("/slices/<job_id>/events")
    def events(job_id):
        if pool.get(job_id) is None:
            return unknown(job_id)

        def stream():
            for report in pool.follow(job_id):
                yield f"id: {report['sequence']}\nevent: progress\ndata: {json.dumps(report)}\n\n"
        return Response(stream(), mimetype="text/event-stream", headers={"Cache-Control": "no-store"})

    @app.delete("/slices/<job_id>")
    def cancel(job_id):
        answer = pool.cancel(job_id)
        if answer == "unknown":
            return unknown(job_id)
        return jsonify({"job": job_id, "cancel": answer, "progress": pool.get(job_id)})

    @app.get("/slices/<job_id>/file")
    def sliced_file(job_id):
        result, refusal = finished(job_id)
        if refusal:
            return refusal
        try:
            return send_file(result["path"], mimetype="application/octet-stream", as_attachment=True,
                             download_name=result["file"])
        except OSError as exc:
            return gone(job_id, exc)

    @app.get("/slices/<job_id>/summary")
    def summary(job_id):
        result, refusal = finished(job_id)
        if refusal:
            return refusal
        if not Path(result["path"]).is_file():
            return gone(job_id, FileNotFoundError(result["path"]))
        # json.dumps, not jsonify: the fields keep the contract's order (jsonify sorts them).
        return Response(json.dumps(result["summary"]), mimetype="application/json")

    return app
