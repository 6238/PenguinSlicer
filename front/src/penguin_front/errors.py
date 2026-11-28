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
}


def error_report(code, detail, where=None, action=None):
    """The error report for `code`, with `detail` for the server log."""
    entry = FRONT_REPORTS[code]
    report = {"code": code, "message": entry["message"]}
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

    def __init__(self, code, detail, where=None, action=None):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.status = FRONT_REPORTS[code]["status"]
        self.report = error_report(code, detail, where, action)
