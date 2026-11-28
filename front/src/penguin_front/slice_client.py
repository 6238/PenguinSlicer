"""The front server's client for the slice service's HTTP interface (README-details.md, "The
slice service's requests"; contracts/slice-http-interface.md).

The front server is the slice service's only caller. A slice service that does not answer
(no connection, a connection cut, no answer within `SLICE_TIMEOUT_S`) is `SliceUnreachable`,
which a request answers `503` `front.slice_unreachable`, a quiet retry for the page. The
answer's bytes come back exactly as the slice service sent them, compressed or not, so that
what is passed to the page is passed unchanged.
"""

from dataclasses import dataclass

import httpx

#: How long the front server waits for the slice service to connect or to send the next
#: bytes of an answer before it takes the slice service as not answering (*proposed*). The
#: slice service answers every request but a progress stream at once, so this is a bound
#: against a hang, far above any honest answer.
SLICE_TIMEOUT_S = 30


class SliceUnreachable(Exception):
    """The slice service did not answer."""


@dataclass(frozen=True)
class Raw:
    """An answer of the slice service: its status, its headers and its bytes as sent."""

    status: int
    headers: httpx.Headers
    body: bytes


class SliceClient:
    def __init__(self, base_url, timeout_s=SLICE_TIMEOUT_S):
        # trust_env off: the slice service's address is used as given, never through a proxy
        # or with credentials that the environment names (HTTP_PROXY, .netrc).
        self._client = httpx.Client(base_url=base_url, timeout=timeout_s, trust_env=False)

    def get_raw(self, path, headers=None):
        """`GET path`, its answer's bytes as sent, not decompressed."""
        try:
            with self._client.stream("GET", path, headers=headers) as answer:
                return Raw(answer.status_code, answer.headers, b"".join(answer.iter_raw()))
        except httpx.TransportError as exc:
            raise SliceUnreachable(f"GET {path}: {type(exc).__name__}: {exc}") from None

    def close(self):
        self._client.close()
