"""The front server's application, and the rules every request meets
(README-details.md, "Rules for every request" and "The version, and old and new versions
together").

- It offers exactly the requests of the contract's table that are built, and answers any
  other path or method `404` `front.no_such_request`: an `OPTIONS` request too, and a path
  differing only by a doubled or trailing slash. A `HEAD` is answered wherever a `GET` is.
- Every failure is an error report as the whole JSON body. A handler refuses by raising
  `FrontError`, or passes another component's report unchanged by raising `PassedReport`. A
  request body that should be JSON and is not is `400` `front.bad_request` (`json_body`). An
  exception inside is `500` `front.unexpected`; its trace goes to the log under an incident
  id that the report's `detail` names.
- Every error report answered writes one log line (`error`): its code, status, method and
  path, the user key and the current group when known, and the page's version when the
  request carries one of the version's form.
- Every answer, whatever its status, carries `X-PenguinSlicer-Version`, and every answer
  except a page file (marked by `page_file`) carries `Cache-Control: no-store`. An answer to
  a signed-in request whose cookie is due carries the cookie moving its thirty days on.
"""

import json
import secrets
import traceback

from flask import Flask, Response, g, request
from werkzeug.exceptions import HTTPException, MethodNotAllowed, NotFound

from . import asking, configuration, identity, pages, parts, settings_table, slices, streams
from .streams import Streams
from .answers import json_body, page_file, target_path as _path  # noqa: F401 - used by tests
from .buckets import FolderBucket
from .context import EXTENSION
from .cookie import CookieKey
from .errors import FrontError, PassedReport, error_report
from .following import Follower
from .ratelimit import RateLimit
from .slice_client import SliceClient
from .version import is_version, version_at

VERSION_HEADER = "X-PenguinSlicer-Version"
PAGE_HEADER = "X-PenguinSlicer-Page"
#: The bytes of a cookie key made at start, when none is given (the development identity on).
MADE_KEY_BYTES = 32


def create_app(settings, *, clock, log, version=None, state_bucket=None, slice_client=None):
    """The front server's application. `log` takes `write(event, **fields)`; `version` is
    the release's, or else the settings', or else the one made from this moment;
    `state_bucket` is the state bucket, or else the folder of the settings; `slice_client`
    the client for the slice service, or else one for the settings' address.

    The wizard's page files are read here, once; a folder that cannot be served raises
    `pages.PagesUnusable`, which stops the start. With no cookie key given (allowed only with
    the development identity on), a key is made here and kept in memory only (the start says
    so in its `cookie_key_made` line): a restart then makes every cookie unreadable, and the
    page's trip signs the development identity in again at once."""
    app = Flask("penguin_front", static_folder=None)
    version = version or settings.version or version_at(clock.now())
    if settings.cookie_key is not None:
        cookie_key = CookieKey(settings.cookie_key)
    else:
        cookie_key = CookieKey(secrets.token_bytes(MADE_KEY_BYTES))
    app.extensions[EXTENSION] = {
        "settings": settings, "clock": clock, "log": log, "version": version,
        "cookie_key": cookie_key,
        "pages": pages.load_pages(settings.wizard_dist, version),
        "state_bucket": state_bucket or FolderBucket(settings.state_dir, clock),
        "slice": slice_client or SliceClient(settings.slice_url),
        "part_uploads": RateLimit(clock, parts.PART_UPLOADS_PER_MINUTE),
        "part_uploads_per_minute": parts.PART_UPLOADS_PER_MINUTE,
        "submissions": RateLimit(clock, slices.SUBMISSIONS_PER_MINUTE),
        "submissions_per_minute": slices.SUBMISSIONS_PER_MINUTE,
    }
    ctx = app.extensions[EXTENSION]
    ctx["follower"] = Follower(clock=clock, slice_client=ctx["slice"],
                               bucket=ctx["state_bucket"], log=log)
    ctx["streams"] = Streams(clock)
    for part in (pages, identity, configuration, settings_table, parts, slices, asking,
                 streams):
        part.register(app)

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
        response = _answer_report(log, error.status, error.report)
        response.headers.update(error.headers)
        return response

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


def _answer_report(log, status, report, body=None, **extra):
    """Answer `report` (as `body` when another component's bytes are passed unchanged),
    writing its `error` line, with the user key and the current group when known."""
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
