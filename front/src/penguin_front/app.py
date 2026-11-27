"""The front server's application, and the rules every request meets
(README-details.md, "Rules for every request" and "The version, and old and new versions
together").

- It offers exactly the requests of the contract's table that are built, and answers any
  other path or method `404` `front.no_such_request`: an `OPTIONS` request too, and a path
  differing only by a doubled or trailing slash. A `HEAD` is answered wherever a `GET` is.
- Every failure is an error report as the whole JSON body. A handler refuses by raising
  `FrontError`. A request body that should be JSON and is not is `400` `front.bad_request`
  (`json_body`). An exception inside is `500` `front.unexpected`; its trace goes to the log
  under an incident id that the report's `detail` names.
- Every error report answered writes one log line (`error`): its code, status, method and
  path, and the page's version when the request carries one of the version's form.
- Every answer, whatever its status, carries `X-PenguinSlicer-Version`, and every answer
  except a page file (marked by `page_file`) carries `Cache-Control: no-store`.
"""

import json
import secrets
import traceback

from flask import Flask, Response, request
from werkzeug.exceptions import HTTPException, MethodNotAllowed, NotFound

from .errors import FrontError, error_report
from .version import is_version, version_at

VERSION_HEADER = "X-PenguinSlicer-Version"
PAGE_HEADER = "X-PenguinSlicer-Page"
EXTENSION = "penguin_front"


def create_app(settings, *, clock, log, version=None):
    """The front server's application. `log` takes `write(event, **fields)`; `version` is
    the release's, or else the settings', or else the one made from this moment."""
    app = Flask("penguin_front", static_folder=None)
    app.url_map.merge_slashes = False
    app.extensions[EXTENSION] = {
        "settings": settings, "clock": clock, "log": log,
        "version": version or settings.version or version_at(clock.now()),
    }

    @app.before_request
    def no_options():
        if request.method == "OPTIONS":
            raise FrontError("front.no_such_request",
                             f"{request.method} {request.path} is not offered")

    @app.errorhandler(FrontError)
    def refused(error):
        return _answer_report(log, error.status, error.report)

    @app.errorhandler(Exception)
    def failed(exc):
        if isinstance(exc, (NotFound, MethodNotAllowed)):
            return _answer_report(log, 404, error_report(
                "front.no_such_request", f"{request.method} {request.path} is not offered"))
        if isinstance(exc, HTTPException) and exc.code < 500:
            return _answer_report(log, 400, error_report(
                "front.bad_request", f"{exc.code} {exc.name}: {exc.description}"))
        incident = secrets.token_hex(6)
        trace = "".join(traceback.format_exception(exc))
        return _answer_report(log, 500, error_report(
            "front.unexpected", f"unexpected failure, incident {incident}; its trace is in "
                                "the server log"), incident=incident, trace=trace)

    @app.after_request
    def every_answer(response):
        response.headers[VERSION_HEADER] = app.extensions[EXTENSION]["version"]
        if not getattr(response, "penguin_page_file", False):
            response.headers["Cache-Control"] = "no-store"
        return response

    return app


def page_file(response, cache_control):
    """Mark `response` as a page file, kept as `cache_control` says instead of `no-store`."""
    response.headers["Cache-Control"] = cache_control
    response.penguin_page_file = True
    return response


def json_body():
    """The request's body read as JSON, whatever its Content-Type says; a body that is not
    JSON (empty, cut short, not UTF-8, or using NaN or Infinity) is `front.bad_request`."""
    raw = request.get_data(cache=True)

    def no_constants(name):
        raise ValueError(f"{name} is not JSON")

    try:
        return json.loads(raw.decode("utf-8"), parse_constant=no_constants)
    except (UnicodeDecodeError, ValueError) as exc:
        raise FrontError("front.bad_request", f"the body is not JSON: {exc}") from None


def _answer_report(log, status, report, **extra):
    line = {"code": report["code"], "status": status, "method": request.method,
            "path": request.path}
    page = request.headers.get(PAGE_HEADER, "")
    if is_version(page):
        line["page_version"] = page
    if status != 500:
        line["detail"] = report["detail"]
    log.write("error", **line, **extra)
    return Response(json.dumps(report), status, mimetype="application/json")
