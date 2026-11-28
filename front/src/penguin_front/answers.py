"""What every request's code shares in reading a request and marking an answer
(README-details.md, "Rules for every request"): the body read as JSON, the path of the
request's target as sent, and the mark of a page file."""

import json
import math

from flask import request

from .errors import FrontError


def page_file(response, cache_control):
    """Mark `response` as a page file, kept as `cache_control` says instead of `no-store`."""
    response.headers["Cache-Control"] = cache_control
    response.penguin_page_file = True
    return response


def json_body(raw=None):
    """The request's body (or `raw`, its bytes as already read) read as JSON, whatever its
    Content-Type says; a body that is not
    JSON (empty, cut short, not UTF-8, or using NaN or Infinity) is `front.bad_request`, as is
    one nested too deeply for the reader, whether or not it is whole, and one holding a number
    too large for a float (`1e999`), which would be read as an infinity no answer could
    hold."""
    raw = request.get_data(cache=True) if raw is None else raw

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


def target_path():
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
