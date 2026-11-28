"""The front server's client for the slice service's HTTP interface (README-details.md, "The
slice service's requests"; contracts/slice-http-interface.md).

The front server is the slice service's only caller. A slice service that does not answer
(no connection, a connection cut, no answer within `SLICE_TIMEOUT_S`) is `SliceUnreachable`,
which a request answers `503` `front.slice_unreachable`, a quiet retry for the page. The
answer's bytes come back exactly as the slice service sent them, compressed or not, so that
what is passed to the page is passed unchanged. Every request about a part or a slice job
carries the user key in `USER_KEY_HEADER`, which only the front server's own code sets: no
header of the browser's is ever passed on.
"""

import json
from contextlib import contextmanager
from dataclasses import dataclass

import httpx

from .errors import PassedReport

#: How long the front server waits for the slice service to connect or to send the next
#: bytes of an answer before it takes the slice service as not answering (*proposed*). The
#: slice service answers every request but a progress stream at once, and repeats its latest
#: report every 15 seconds on a quiet stream, so this is a bound against a hang, far above
#: any honest answer.
SLICE_TIMEOUT_S = 30
#: The header that tells the slice service whose part or slice job a request is about.
USER_KEY_HEADER = "X-Penguin-User-Key"


class SliceUnreachable(Exception):
    """The slice service did not answer."""


@dataclass(frozen=True)
class Raw:
    """An answer of the slice service: its status, its headers and its bytes as sent."""

    status: int
    headers: httpx.Headers
    body: bytes


class SliceClient:
    def __init__(self, base_url, timeout_s=SLICE_TIMEOUT_S, transport=None):
        """`transport` replaces the network in a test, which then raises what a silent or
        cut-off slice service would make the network raise."""
        # trust_env off: the slice service's address is used as given, never through a proxy
        # or with credentials that the environment names (HTTP_PROXY, .netrc).
        self._client = httpx.Client(base_url=base_url, timeout=timeout_s, trust_env=False,
                                    transport=transport)

    def get_raw(self, path, headers=None):
        """`GET path`, its answer's bytes as sent, not decompressed."""
        return self.send("GET", path, headers=headers)

    def send(self, method, path, *, headers=None, params=None, content=None):
        """`method path` with `content` (bytes, or an iterable of byte pieces passed on as
        they come, which then needs `Content-Length` in `headers`), its answer's bytes as
        sent. Unless `headers` says otherwise the answer is asked for uncompressed. A failure
        of `content` itself (the browser's upload cut short) is raised as it is."""
        headers = {"Accept-Encoding": "identity", **(headers or {})}
        try:
            with self._client.stream(method, path, headers=headers, params=params,
                                     content=content) as answer:
                return Raw(answer.status_code, answer.headers, b"".join(answer.iter_raw()))
        except httpx.TransportError as exc:
            raise SliceUnreachable(f"{method} {path}: {type(exc).__name__}: {exc}") from None

    @contextmanager
    def stream(self, path, headers=None):
        """`GET path` held open: the httpx answer, to read in pieces (a progress stream, a
        sliced file). Not answering, before the answer starts, is `SliceUnreachable`; a
        failure while it is read is httpx's own `TransportError`, for the reader."""
        headers = {"Accept-Encoding": "identity", **(headers or {})}
        try:
            context = self._client.stream("GET", path, headers=headers)
            answer = context.__enter__()
        except httpx.TransportError as exc:
            raise SliceUnreachable(f"GET {path}: {type(exc).__name__}: {exc}") from None
        try:
            yield answer
        finally:
            context.__exit__(None, None, None)

    def close(self):
        self._client.close()


def user_key_header(user_key):
    return {USER_KEY_HEADER: user_key}


def slice_report(body):
    """The slice service's error report in `body`, or None."""
    try:
        report = json.loads(body)
    except ValueError:
        return None
    if isinstance(report, dict) and isinstance(report.get("code"), str) \
            and report["code"].startswith("slice."):
        return report
    return None


def refusal(raw, what):
    """What a failure answer of the slice service becomes for the page: its own error report,
    passed byte for byte with its status (`PassedReport`); or, for `slice.no_user_key` (a
    fault of the front server's) and for an answer that is not the slice service's report, a
    failure inside the front server, answered `500` `front.unexpected`."""
    report = slice_report(raw.body) if raw.headers.get("Content-Encoding") is None else None
    if report is None:
        return RuntimeError(f"{what}: the slice service answered {raw.status} with neither "
                            f"its answer nor its own error report: {raw.body[:200]!r}")
    if report["code"] == "slice.no_user_key":
        return RuntimeError(f"{what}: the slice service answered slice.no_user_key: the "
                            "front server sent no user key")
    return PassedReport(raw.status, raw.body, report)
