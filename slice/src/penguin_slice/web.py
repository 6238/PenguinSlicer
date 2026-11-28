"""The slice service's HTTP interface, its one interface: a Flask app factory
(contracts/slice-http-interface.md).

    POST   /parts?units=mm|in     one part's binary STL as the body: checked and kept in the
                                  part store; 201 with the part's record
    POST   /slices                a plate configuration as a JSON body, its parts named by
                                  hash and units: 202 with the slice job
    GET    /slices/<job>          the slice job's latest progress report
    GET    /slices/<job>/events   the slice job's progress reports as a stream
                                  (text/event-stream), the latest first, ending with the final one
    DELETE /slices/<job>          cancel the slice job: {"cancel": cancelled|cancelling|finished}
    GET    /slices/<job>/file     the sliced file of a done slice job, and nothing else
    GET    /slices/<job>/summary  the sliced file's summary (contracts/sliced-file.md), as JSON

Every one of these requests carries the user key in the header X-Penguin-User-Key: the
front server's word for whose part or slice job it is. A request without it, or with an
empty one, is refused (slice.no_user_key). A part is kept, and a slice job held, under the
user key that sent it; a request about another user key's slice job is answered exactly as
one about an unknown slice job, and logged as a refusal.

Every answer that is not a success is an error report (contracts/error-report.md), with
an HTTP status: 400 for a request without the user key, a part without its units, or a
body that is not a plate configuration; 404 for an unknown slice job or a path not offered;
405 for a method a path does not take; 409 for a sliced file or summary that is not there
(yet); 410 for a sliced file gone from the disk; 413 for a part or a plate configuration
too large, refused before its body is read; 422 for a part or plate configuration a check
refused; 500 for the slice service's own failure (its work folder or part store not
writable, a bug); 503 when the queue is full.

Each part is checked when it arrives, and each plate configuration when it arrives, before
a slice job is queued for it, so a refusal comes back at once. A slice job's files live under
`work_dir/<job folder>/`: its hold on each of its parts' files (`parts/`), the scratch folder
of the slice, and the sliced file, all removed when the slice job ends without a file or
when its record expires. The part store is a folder of its own under `work_dir`, new in each
process. At start the app refuses a bad setting (limits.SettingError), removes the scratch
and the part store left by a process that died (service.clean_stale_scratch) and starts the
job pool's sweeper, which sweeps the part store too.

One app runs in one slice service process, and its slice jobs live in this process's
memory (jobs.JobPool): a client must keep talking to the slice service process that
accepted its slice job, and a server that runs several worker processes behind one
address loses slice jobs.
"""
import json
import shutil
import tempfile
import traceback
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_file
from werkzeug.exceptions import HTTPException

from . import limits, part_store
from .errors import error_report, report_for_code
from .jobs import FINAL, JobPool, QueueFull, SafeLog, exception_text
from .mesh import MeshError
from .service import (BAD_CONFIGURATION_MESSAGE, UPLOAD_REMEDIES, clean_stale_scratch, make_scratch, parts_missing,
                      read_plate_configuration, slice_plate_configuration, upload_part)
from .slicer import CANCELLED_MESSAGE, SCRATCH_UNWRITABLE_MESSAGE

USER_KEY_HEADER = "X-Penguin-User-Key"
UNKNOWN_JOB_MESSAGE = "The print server does not know this slice; it may have expired."
NOT_READY_MESSAGE = "The sliced file is not ready yet."
NOT_OFFERED_MESSAGE = "The print server does not offer {method} {path}."
FILE_GONE_MESSAGE = "The sliced file is no longer on the print server."
NO_USER_KEY_MESSAGE = "The slicer was not told whose request this is."
BAD_UNITS_MESSAGE = "The slicer was not told whether this part is in millimetres or inches."
NO_LENGTH_MESSAGE = "The slicer was not told how large this part is."
PART_STORE_UNWRITABLE_MESSAGE = "The slicer could not keep this part."
UPLOAD_NOT_WHOLE_MESSAGE = "This part did not arrive whole."
TOO_LARGE_PROBLEM = f"it is larger than {limits.MAX_PLATE_CONFIGURATION_BYTES:,} bytes"
JOB_PARTS = "parts"           # a slice job's hold on its parts' files, in its folder
STORE_LABEL = "parts-"        # the part store's folder: slice-<pid>-<start>-parts-<random>
LOGGED_ENTRIES = 100          # parts listed in a refusal's log line, at most
LOGGED_USER_KEY_CHARS = 200   # a user key as a log line carries it, at most
# The most of a body Flask reads at all, behind the routes' own checks of Content-Length: a
# plate configuration sent without one is read no further than this, then refused for its size.
MAX_BODY_BYTES = max(limits.MAX_PART_BYTES, limits.MAX_PLATE_CONFIGURATION_BYTES)


def _report(code, message, detail="", status=400, where=None):
    return jsonify(report_for_code(code, message, detail, where)), status


def _status_for(report):
    if report["code"] == "slice.bad_plate_configuration":
        return 400
    if report["code"] == "slice.part_too_detailed":
        return 413
    return 422 if report["where"]["stage"] == "checking" else 500


def _parts_named(data, limit=LOGGED_ENTRIES):
    """The parts a plate configuration names, for the log line of a refusal: {key: {name,
    sha256, units}}, or None when it names none that can be read."""
    parts = data.get("parts") if isinstance(data, dict) else None
    if not isinstance(parts, dict):
        return None
    return {str(key)[:64]: {field: str(part.get(field))[:80] for field in ("name", "sha256", "units")}
            if isinstance(part, dict) else {"name": None, "sha256": None, "units": None}
            for key, part in list(parts.items())[:limit]}


def _for_upload(body):
    """An answer to POST /parts: the remedy of service.UPLOAD_REMEDIES (about adding the part,
    never about a slice) and no action, whatever answered it."""
    body["remedy"] = UPLOAD_REMEDIES.get(body["code"], UPLOAD_REMEDIES["slice.unexpected"])
    body.pop("action", None)
    return body


def _logged(user_key):
    return None if user_key is None else user_key[:LOGGED_USER_KEY_CHARS]


def slice_worker(job_id, configuration, context):
    """The pool's worker: slice a checked PlateConfiguration into its slice job's folder."""
    out = configuration.work_dir / "out"
    sliced = slice_plate_configuration(configuration, out, stop=context.stop, on_progress=context.progress)
    result = {"path": str(sliced.path), "summary": sliced.summary, "file": sliced.path.name,
              "peak_rss_kb": sliced.peak_rss_kb, "orca_wall_s": sliced.wall_s,
              "work_dir": str(configuration.work_dir)}
    for key in ("memory_note", "stop_note"):
        if getattr(sliced, key):
            result[key] = getattr(sliced, key)
    return result


def remove_job_files(configuration):
    """The pool's cleanup: a slice job's folder (its hold on its parts, its scratch, its sliced file)."""
    if configuration is not None and configuration.work_dir is not None:
        shutil.rmtree(configuration.work_dir, ignore_errors=True)


def create_app(work_dir=None, pool=None, *, log=None, start_sweeper=True, environ=None, store=None):
    """The app. `work_dir` holds every slice job's files and the part store (a new temporary
    folder when None); `pool` is a JobPool whose worker is slice_worker (made here when
    None); `store` is the part store (made here, in a new folder of `work_dir`, when None);
    `log` takes the pool's log lines (dicts), through jobs.SafeLog, so a log that fails never
    changes an answer or a slice job: the pool made here counts those failures
    (JobPool.log_failures). Raises limits.SettingError, before anything else, for a setting
    it refuses."""
    limits.max_peak_mb(environ)          # a bad setting stops the service at start
    store_bytes = part_store.max_bytes(environ)
    work_dir = Path(work_dir or tempfile.mkdtemp(prefix="penguin-slice-")).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    log = log if isinstance(log, SafeLog) else SafeLog(log or (lambda entry: None))     # a failing sink is counted
    clean_stale_scratch(work_dir)
    if store is None:
        store = part_store.PartStore(make_scratch(work_dir, STORE_LABEL), store_bytes)

    pool = pool or JobPool(slice_worker, error_report=error_report, cleanup=remove_job_files, log=log)
    if start_sweeper:
        pool.start_sweeper(also=(store.sweep,))
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_BODY_BYTES
    app.extensions["penguin_slice_pool"] = pool
    app.extensions["penguin_slice_store"] = store

    @app.after_request
    def no_store(answer):
        answer.headers["Cache-Control"] = "no-store"         # every answer (the contract's rules)
        return answer

    def submitting():
        return request.method == "POST" and request.path == "/slices"

    def uploading():
        return request.method == "POST" and request.path == "/parts"

    def asked_key():
        return request.headers.get(USER_KEY_HEADER)

    def log_refusal(body, status, data=None, extra=None):
        """The log line of a plate configuration refused before any slice job existed for it:
        every refusal at POST /slices, whatever the step that refused it (slice jobs are the
        pool's to log)."""
        log({"event": "slice_job", "job": None, "state": "refused", "user_key": _logged(asked_key()),
             "http_status": status, "error_code": body["code"], "error_detail": body["detail"],
             "parts": _parts_named(data), "bytes": request.content_length, **(extra or {})})

    def log_upload(state, status, body=None, record=None, extra=None):
        """The log line of every upload of a part: stored (new or again) or refused."""
        entry = {"event": "part_upload", "state": state, "user_key": _logged(asked_key()), "http_status": status,
                 "units": request.args.get("units", "")[:20], "bytes": request.content_length}
        if record is not None:
            entry.update(sha256=record["sha256"], triangles=record["measurements"]["triangles"],
                         size_mm=record["measurements"]["size_mm"], warnings=[w["code"] for w in record["warnings"]])
        if body is not None:
            entry.update(error_code=body["code"], error_detail=body["detail"])
        log({**entry, **(extra or {})})

    def log_answered(body, status, extra=None):
        if submitting():
            log_refusal(body, status, extra=extra)
        elif uploading():
            log_upload("refused", status, body, extra=extra)

    @app.errorhandler(HTTPException)
    def not_offered(error):
        # No such path (404), a method a path does not take (405), and the rest of Flask's own.
        body = report_for_code("slice.bad_request", NOT_OFFERED_MESSAGE.format(method=request.method,
                                                                               path=request.path[:80]),
                               f"HTTP {error.code} {error.name}")
        if uploading():          # POST /parts is offered: Flask's error is about its body (one cut off)
            body["message"] = UPLOAD_NOT_WHOLE_MESSAGE
            _for_upload(body)
        log_answered(body, error.code)
        return jsonify(body), error.code

    @app.errorhandler(Exception)
    def unexpected(error):
        body = error_report(error)
        trace = traceback.format_exc()[-2000:]
        if uploading():
            _for_upload(body)
        if submitting() or uploading():
            log_answered(body, 500, extra={"traceback": trace})
        else:
            log({"event": "slice_http_error", "path": request.path[:80], "error": exception_text(error),
                 "user_key": _logged(asked_key()), "error_code": body["code"], "traceback": trace})
        return jsonify(body), 500

    def no_user_key():
        """The refusal of a request without the user key, logged, or None when it has one."""
        key = asked_key()
        if key:
            return None
        detail = f"{request.method} {request.path[:80]} " + \
            (f"without {USER_KEY_HEADER}" if key is None else f"with an empty {USER_KEY_HEADER}")
        body = report_for_code("slice.no_user_key", NO_USER_KEY_MESSAGE, detail)
        if submitting():
            log_refusal(body, 400)
        elif uploading():
            log_upload("refused", 400, _for_upload(body))
        else:
            log({"event": "slice_http_refused", "path": request.path[:80], "user_key": None, "http_status": 400,
                 "error_code": body["code"], "error_detail": detail})
        return jsonify(body), 400

    @app.post("/parts")
    def upload():
        refusal = no_user_key()
        if refusal:
            return refusal
        units, length = request.args.get("units"), request.content_length
        if units not in part_store.UNITS:
            detail = "no units label" if units is None else f"units {units[:40]!r}, not 'mm' or 'in'"
            body, status = report_for_code("slice.bad_units", BAD_UNITS_MESSAGE, detail), 400
        elif length is None:
            body, status = report_for_code("slice.bad_request", NO_LENGTH_MESSAGE, "upload without Content-Length"), 400
        elif length > limits.MAX_PART_BYTES:
            body, status = report_for_code("slice.part_too_detailed",
                                           limits.TOO_DETAILED_BYTES_MESSAGE.format(name="This part"),
                                           f"upload Content-Length {length:,} bytes, cap {limits.MAX_PART_BYTES:,}"), 413
        else:
            try:
                record, _entry, new = upload_part(store, asked_key(), units, request.get_data(cache=False))
            except MeshError as exc:
                body = error_report(exc)
                status = _status_for(body)
            except OSError as exc:
                body, status = report_for_code("slice.scratch_unwritable", PART_STORE_UNWRITABLE_MESSAGE,
                                               f"{type(exc).__name__}: {exc}"[:500]), 500
            except Exception as exc:          # a server profile that cannot be read
                body = error_report(exc)
                if body["code"] == "slice.unexpected":
                    raise
                status = _status_for(body)
            else:
                log_upload("stored" if new else "stored_again", 201, record=record)
                return jsonify(record), 201
        log_upload("refused", status, _for_upload(body))
        return jsonify(body), status

    @app.post("/slices")
    def submit():
        refusal = no_user_key()
        if refusal:
            return refusal
        data, length = None, request.content_length
        cap = limits.MAX_PLATE_CONFIGURATION_BYTES
        if request.mimetype.startswith("multipart/"):
            problem = "it is a multipart form, not a JSON body"
            body, status = report_for_code("slice.bad_plate_configuration",
                                           BAD_CONFIGURATION_MESSAGE.format(problem=problem), problem), 400
        elif length is not None and length > cap:
            body, status = report_for_code("slice.bad_plate_configuration",
                                           BAD_CONFIGURATION_MESSAGE.format(problem=TOO_LARGE_PROBLEM),
                                           f"plate configuration Content-Length {length:,} bytes, cap {cap:,}"), 413
        else:
            raw = request.get_data(cache=False)
            if len(raw) > cap:
                body, status = report_for_code("slice.bad_plate_configuration",
                                               BAD_CONFIGURATION_MESSAGE.format(problem=TOO_LARGE_PROBLEM),
                                               f"plate configuration of {len(raw):,} bytes, cap {cap:,}"), 413
            else:
                try:
                    data = json.loads(raw)
                except (ValueError, RecursionError) as exc:
                    problem = "it is not JSON"
                    body, status = report_for_code("slice.bad_plate_configuration",
                                                   BAD_CONFIGURATION_MESSAGE.format(problem=problem),
                                                   f"{type(exc).__name__}: {exc}"[:300]), 400
                else:
                    body, status = _queue(data, asked_key())
        if status != 202:
            log_refusal(body, status, data)
        return jsonify(body), status

    def _queue(data, user_key):
        """Check the plate configuration, hold its parts and queue its slice job: (answer, status)."""
        try:
            configuration = read_plate_configuration(data, lambda sha256, units: store.get(user_key, sha256, units),
                                                     environ=environ)
        except Exception as exc:
            body = error_report(exc)
            if body["code"] == "slice.unexpected":
                raise
            return body, _status_for(body)
        try:
            job_dir = make_scratch(work_dir)
        except OSError as exc:
            return report_for_code("slice.scratch_unwritable", SCRATCH_UNWRITABLE_MESSAGE,
                                   f"{type(exc).__name__}: {exc}"), 500
        try:
            entries = list(configuration.stored.values())
            held = store.hold(entries, job_dir / JOB_PARTS)
            for part in configuration.parts.values():
                part.stl_path = held[(part.sha256, part.units)]
            store.touch(entries)
            configuration.work_dir = job_dir
            describe = {"user_key": _logged(user_key), **configuration.describe()}
            job_id = pool.submit(configuration, describe=describe, expected_s=configuration.expected_s,
                                 user_key=user_key)
        except part_store.PartsGone as exc:
            shutil.rmtree(job_dir, ignore_errors=True)
            gone = {(e.sha256, e.units) for e in exc.entries}
            missing = [{"key": ref, "sha256": part.sha256, "units": part.units}
                       for ref, part in configuration.parts.items() if (part.sha256, part.units) in gone]
            return error_report(parts_missing(missing)), 422
        except QueueFull as exc:
            shutil.rmtree(job_dir, ignore_errors=True)
            return error_report(exc), 503
        except OSError as exc:
            shutil.rmtree(job_dir, ignore_errors=True)
            return report_for_code("slice.scratch_unwritable", SCRATCH_UNWRITABLE_MESSAGE,
                                   f"holding the parts: {type(exc).__name__}: {exc}"), 500
        except BaseException:
            shutil.rmtree(job_dir, ignore_errors=True)
            raise
        return {"job": job_id, "plate_id": configuration.plate_id, "submission_id": configuration.submission_id,
                "progress": pool.get(job_id), "part_warnings": configuration.part_warnings()}, 202

    def unknown(job_id):
        return _report("slice.unknown_job", UNKNOWN_JOB_MESSAGE, f"job {job_id[:40]!r}", 404)

    def not_theirs(job_id):
        """None when the request may see the slice job; else the answer for an unknown slice
        job: no user key, a slice job unknown, or another user key's (logged as a refusal)."""
        refusal = no_user_key()
        if refusal:
            return refusal
        key = asked_key()
        if pool.owned_by(job_id, key):
            return None
        if pool.get(job_id) is not None:
            log({"event": "slice_http_refused", "path": request.path[:80], "method": request.method,
                 "job": job_id[:40], "user_key": _logged(key), "http_status": 404, "error_code": "slice.unknown_job",
                 "error_detail": "a slice job of another user key"})
        return unknown(job_id)

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
        refusal = not_theirs(job_id)
        if refusal:
            return refusal
        report = pool.get(job_id)
        return jsonify(report) if report else unknown(job_id)

    @app.get("/slices/<job_id>/events")
    def events(job_id):
        refusal = not_theirs(job_id)
        if refusal:
            return refusal

        def stream():
            for report in pool.follow(job_id):
                yield f"id: {report['sequence']}\nevent: progress\ndata: {json.dumps(report)}\n\n"
        return Response(stream(), mimetype="text/event-stream", headers={"Cache-Control": "no-store"})

    @app.delete("/slices/<job_id>")
    def cancel(job_id):
        refusal = not_theirs(job_id)
        if refusal:
            return refusal
        answer = pool.cancel(job_id)
        if answer == "unknown":
            return unknown(job_id)
        return jsonify({"job": job_id, "cancel": answer, "progress": pool.get(job_id)})

    @app.get("/slices/<job_id>/file")
    def sliced_file(job_id):
        refusal = not_theirs(job_id)
        if refusal:
            return refusal
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
        refusal = not_theirs(job_id)
        if refusal:
            return refusal
        result, refusal = finished(job_id)
        if refusal:
            return refusal
        if not Path(result["path"]).is_file():
            return gone(job_id, FileNotFoundError(result["path"]))
        # json.dumps, not jsonify: the fields keep the contract's order (jsonify sorts them).
        return Response(json.dumps(result["summary"]), mimetype="application/json")

    return app
