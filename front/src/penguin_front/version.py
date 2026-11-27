"""The version on every answer (README-details.md, "The version, and old and new versions
together"): `YYYYMMDDTHHMMSSZ-<commit>`, the moment the release was built in UTC, then the
first seven characters of its commit. A release build sets it in `PENGUIN_VERSION`; unset,
as when run from a checkout, it is the moment the front server started, then `-0000000`."""

import re
from datetime import datetime, timezone

VERSION_FORM = re.compile(r"\d{8}T\d{6}Z-[0-9a-f]{7}")
NO_COMMIT = "0000000"


def is_version(text):
    return VERSION_FORM.fullmatch(text) is not None


def version_at(moment):
    """The version of a front server started from a checkout at `moment` (epoch seconds)."""
    stamp = datetime.fromtimestamp(moment, timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{NO_COMMIT}"
