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
import math
import secrets
import traceback

from flask import Flask, Response, g, request
from werkzeug.exceptions import HTTPException, MethodNotAllowed, NotFound

from . import identity
from .buckets import FolderBucket
from .context import EXTENSION
from .cookie import CookieKey
from .errors import FrontError, PassedReport, error_report
from .version import is_version, version_at

VERSION_HEADER = "X-PenguinSlicer-Version"
PAGE_HEADER = "X-PenguinSlicer-Page"
#: The bytes of a cookie key made at start, when none is given (the development identity on).
MADE_KEY_BYTES = 32


def create_app(settings, *, clock, log, version=None, state_bucket=None):
    """The front server's application. `log` takes `write(event, **fields)`; `version` is
    the release's, or else the settings', or else the one made from this moment;
    `state_bucket` is the state bucket, or else the folder of the settings.

    With no cookie key given (allowed only with the development identity on), a key is made
    here and kept in memory only (the start says so in its `cookie_key_made` line): a
    restart then makes every cookie unreadable, and the page's trip signs the development
    identity in again at once."""
    app = Flask("penguin_front", static_folder=None)
    if settings.cookie_key is not None:
        cookie_key = CookieKey(settings.cookie_key)
    else:
        cookie_key = CookieKey(secrets.token_bytes(MADE_KEY_BYTES))
    app.extensions[EXTENSION] = {
        "settings": settings, "clock": clock, "log": log,
        "version": version or settings.version or version_at(clock.now()),
        "cookie_key": cookie_key,
        "state_bucket": state_bucket or FolderBucket(settings.state_dir, clock),
    }
    identity.register(app)

    @app.before_request
    def not_offered():
        # A doubled slash anywhere is refused here, before the handler runs, on the path of
        # the request's target as sent: waitress drops a path's leading slashes before the
        # application sees it (so `//x` would be served as `/x`), a target without a leading
        # slash would be served as if it had one, and the web framework answers a doubled
        # slash elsewhere with a redirect. An encoded slash (`%2F`) is refused anywhere: the
        # server decodes it into a slash, so `/t%2Fx` would be served as `/t/x`, and no path
        # of the contract's table holds one.
        sent = _path()
        if request.method == "OPTIONS" or not sent.startswith("/") or "//" in sent \
                or "%2f" in sent.lower() or "//" in request.environ.get("PATH_INFO", ""):
            raise FrontError("front.no_such_request",
                             f"{request.method} {_path()} is not offered")

    @app.errorhandler(FrontError)
    def refused(error):
        return _answer_report(log, error.status, error.report)

    @app.errorhandler(PassedReport)
    def passed(error):
        return _answer_report(log, error.status, error.report, body=error.body)

    @app.errorhandler(Exception)
    def failed(exc):
        if isinstance(exc, (NotFound, MethodNotAllowed)):
            return _answer_report(log, 404, error_report(
                "front.no_such_request", f"{request.method} {_path()} is not offered"))
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
        identity.extend_cookie(response)
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
    JSON (empty, cut short, not UTF-8, or using NaN or Infinity) is `front.bad_request`, as is
    one nested too deeply for the reader, whether or not it is whole, and one holding a number
    too large for a float (`1e999`), which would be read as an infinity no answer could
    hold."""
    raw = request.get_data(cache=True)

    def no_constants(name):
        raise ValueError(f"{name} is not JSON")

    def finite(text):
        number = float(text)
        if not math.isfinite(number):
            raise ValueError(f"the number {text[:40]} is too large for the server to read")
        return number

    try:
        return json.loads(raw.decode("utf-8"), parse_constant=no_constants,
                          parse_float=finite)
    except (UnicodeDecodeError, ValueError) as exc:
        raise FrontError("front.bad_request", f"the body is not JSON: {exc}") from None
    except RecursionError:
        raise FrontError("front.bad_request",
                         "the body is not JSON the server can read: it is nested too "
                         "deeply") from None


def _path():
    """The path of the request's target as sent, still percent-encoded: the target
    (`REQUEST_URI`, which waitress and the test client both give, else `RAW_URI`) without
    its query or fragment, and in the absolute form (`http://host/path`) without its scheme
    and host. With neither key, the server's decoded `PATH_INFO`."""
    environ = request.environ
    target = environ.get("REQUEST_URI") or environ.get("RAW_URI")
    if target is None:
        return environ.get("PATH_INFO", "")
    target = target.split("#", 1)[0].split("?", 1)[0]
    scheme, sep, rest = target.partition("://")
    if sep and scheme.isalpha():
        slash = rest.find("/")
        target = rest[slash:] if slash >= 0 else ""
    return target


def _answer_report(log, status, report, body=None, **extra):
    """Answer `report` (as `body` when another component's bytes are passed unchanged),
    writing its `error` line: the user key and the current group when known."""
    line = {"code": report["code"], "status": status, "method": request.method,
            "path": _path()}
    who = g.get("penguin_identity")
    if who is not None:
        line["user_key"] = who.user_id
    if g.get("penguin_group") is not None:
        line["group"] = g.penguin_group
    page = request.headers.get(PAGE_HEADER, "")
    if is_version(page):
        line["page_version"] = page
    if status != 500:
        line["detail"] = report.get("detail")
    log.write("error", **line, **extra)
    return Response(body if body is not None else json.dumps(report), status,
                    mimetype="application/json")
