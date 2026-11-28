"""The front server's own error reports (contracts/error-report.md; the codes and statuses
are those of contracts/wizard-front-server.md, "The front server's error reports").

Each code the front server produces has its status, whether it may be retried unchanged,
and its two sentences here. The sentences say "your CAD program", never "Onshape", since a
sentence written on a server cannot know whether the page is inside Onshape; they name
nothing of the front server's insides. A code is added here in the commit that first
produces it, with a test that produces it on purpose (README-details.md, "Error reports").
"""

FRONT_REPORTS = {
    "front.bad_request": {
        "status": 400, "retryable": False,
        "message": "The server could not read this request.",
        "remedy": "Reload the page and try again; if it happens again, PenguinSlicer needs "
                  "fixing.",
    },
    "front.no_such_request": {
        "status": 404, "retryable": False,
        "message": "The server does not offer this request.",
        "remedy": "Reload the page; if it happens again, PenguinSlicer needs fixing.",
    },
    "front.unexpected": {
        "status": 500, "retryable": True,
        "message": "Something went wrong on the server.",
        "remedy": "Your work is kept; try again in a moment.",
    },
    "front.not_signed_in": {
        "status": 401, "retryable": False,
        "message": "You are not signed in to PenguinSlicer in this browser.",
        "remedy": "Sign in again; your parts, layout and settings are kept in this browser.",
    },
    "front.group_not_allowed": {
        "status": 403, "retryable": False,
        "message": "This was asked for a group your sign-in does not include.",
        "remedy": "Choose one of your own groups and try again.",
    },
    "front.configuration_changed": {
        "status": 409, "retryable": False,
        "message": "Someone else changed the configuration before this change was saved, "
                   "so it was not saved.",
        "remedy": "Reload the configuration and make the change again.",
    },
    "front.configuration_invalid": {
        "status": 422, "retryable": False,
        # The message names the first rule broken; this is its frame (configuration.py).
        "message": "The configuration was not saved, because it breaks a rule.",
        "remedy": "Correct the configuration and save it again.",
    },
    "front.slice_unreachable": {
        "status": 503, "retryable": True,
        "message": "The slicer is not answering.",
        "remedy": "Your work is kept; try again in a moment.",
    },
    "front.state_bucket_unreachable": {
        "status": 503, "retryable": True,
        "message": "The server could not reach the store where it keeps configurations and "
                   "sliced files.",
        "remedy": "Your work is kept; try again in a moment.",
    },
    "front.too_many_requests": {
        "status": 429, "retryable": True,
        "message": "This browser sent parts or plates faster than the server takes them.",
        "remedy": "Your work is kept; it is sent again by itself in a moment.",
    },
}


def error_report(code, detail, where=None, action=None, message=None):
    """The error report for `code`, with `detail` for the server log; `message`, when given,
    in place of the code's own sentence, for a report that says what in particular went
    wrong."""
    entry = FRONT_REPORTS[code]
    report = {"code": code, "message": message or entry["message"]}
    if where:
        report["where"] = where
    report["remedy"] = entry["remedy"]
    if action:
        report["action"] = action
    report["retryable"] = entry["retryable"]
    report["detail"] = detail
    return report


class FrontError(Exception):
    """A failure the front server answers with its own error report. Raised anywhere a
    request is being answered; the application turns it into the answer."""

    def __init__(self, code, detail, where=None, action=None, message=None, headers=None):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.status = FRONT_REPORTS[code]["status"]
        self.report = error_report(code, detail, where, action, message)
        #: Headers the answer carries beside the report, such as `Retry-After`.
        self.headers = dict(headers or {})


class PassedReport(Exception):
    """Another component's error report (`report`, read from `body`), answered byte for byte
    as that component gave it, with its status."""

    def __init__(self, status, body, report):
        super().__init__(report["code"])
        self.status = status
        self.body = body
        self.report = report
