"""The daemon's side of the relay protocol. Outbound HTTPS only; no ports are opened on the
Pi and nothing on the school network has to be reachable from outside.

Every method translates an HTTP answer into one of four outcomes the run loop knows how to
handle: a value, TokenRejected (re-exchange), RateLimited (honour Retry-After), or a plain
RelayError (log, back off, try again).
Every answer is checked for its shape before it is used: a web page instead of JSON (a
captive portal or a proxy), truncated JSON, or JSON of the wrong shape is a RelayError
naming what arrived, never an AttributeError deep in the run loop.
"""

import hashlib
import os

import requests

from penguin_delivery_daemon import USER_AGENT


class RelayError(Exception):
    """Any failure talking to the backend. The run loop logs it and backs off."""


class DownloadCorrupt(RelayError):
    """The sliced file arrived, but not as the relay described it: the wrong length or the
    wrong checksum. Retrying may help; starting it would not."""


class Cancelled(Exception):
    """The delivery job was cancelled while its file was downloading."""


class TokenRejected(RelayError):
    """The backend answered 401 with {"error": "repair"}: blank the token and re-exchange.

    Happens after the relay restarts with a different secret key, or when a Pi's code was
    retired.
    """


class RateLimited(RelayError):
    def __init__(self, retry_after):
        super().__init__(f"rate limited, retry after {retry_after}s")
        self.retry_after = retry_after


class ChallengeDetected(RelayError):
    """An HTML body arrived on a JSON route -- almost always a Cloudflare challenge page.

    Named rather than parsed, so `penguincam-printer status` can tell a mentor what is
    actually happening instead of reporting a JSON parse error."""


def _reason(error):
    """A network failure in plain words, so the daemon's log reads as what happened (the
    relay restarted, the name did not resolve) rather than as a traceback-like repr."""
    text = str(error)
    if isinstance(error, requests.exceptions.SSLError):
        return 'the secure connection to the relay failed (TLS)'
    if isinstance(error, requests.exceptions.ConnectTimeout):
        return 'the relay did not accept the connection in time'
    if isinstance(error, requests.exceptions.ReadTimeout):
        return 'the relay did not answer in time'
    if 'RemoteDisconnected' in text or 'Connection aborted' in text:
        return 'the relay closed the connection before answering (it may be restarting)'
    if 'NameResolution' in text or 'Name or service not known' in text or \
            'getaddrinfo' in text:
        return "the relay's name could not be looked up (DNS)"
    if 'Connection refused' in text:
        return 'the relay refused the connection'
    if 'reset' in text.lower():
        return 'the connection to the relay was reset'
    return f'{error.__class__.__name__}: {text.splitlines()[0][:160] if text else ""}'


class RelayClient:
    """One long-lived HTTP session to the backend.

    `backend_url` comes from the Pi's config file, and the daemon joins it with the path a
    job carries, so a development server reached as localhost by the browser and by a LAN
    address from the Pi works with no extra configuration."""

    def __init__(self, backend_url, token=None, *, session=None, timeout=20.0):
        self.backend_url = (backend_url or '').rstrip('/')
        self.token = token or None
        self.timeout = timeout
        self._session = session if session is not None else requests.Session()

    # -- plumbing ----------------------------------------------------------------------

    def _url(self, path):
        return f"{self.backend_url}{path}"

    def _headers(self, *, authorized=True):
        headers = {'User-Agent': USER_AGENT}
        if authorized and self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        return headers

    #: A rate limit longer than this is a configuration accident, not a wait worth
    #: honouring: the run loop sleeps and retries rather than stalling for hours.
    MAX_RETRY_AFTER = 300.0

    @classmethod
    def _retry_after(cls, response):
        """Seconds to wait before retrying, clamped to something a run loop can sleep on."""
        try:
            value = float(response.headers.get('Retry-After', ''))
        except (TypeError, ValueError):
            return 60.0
        return max(0.0, min(value, cls.MAX_RETRY_AFTER))

    def _payload(self, response):
        """The JSON body, or an exception naming what arrived instead."""
        content_type = (response.headers.get('Content-Type') or '').lower()
        if 'json' not in content_type:
            body = (response.text or '').lstrip()[:200]
            raise ChallengeDetected(
                f"expected JSON from the relay, got {content_type or 'no content type'} "
                f"({body!r}). A web page here is usually a captive portal, a proxy or a "
                f"bot challenge between this computer and the relay.")
        try:
            payload = response.json()
        except ValueError as e:
            raise RelayError(f"could not parse the relay's reply: {e}") from e
        if not isinstance(payload, dict):
            raise RelayError(f"the relay's reply was JSON of the wrong shape "
                             f"({type(payload).__name__}, not an object)")
        return payload

    def _check(self, response, what, *, handled=(), parse_body=True):
        """Everything all five calls answer alike, in one place: a rate limit, a challenge
        page, and the generic failure. Returns the status code, so a caller can act on the
        one or two answers it handles itself (`handled`, alongside 200).

        429 is translated before the body is inspected, so a rate-limit page served as HTML
        is reported as the rate limit it is and not as a challenge. `parse_body` is off for
        the download route, whose successful body is a file and never JSON."""
        status = response.status_code
        if status == 429:
            raise RateLimited(self._retry_after(response))
        if status == 200 or status in handled:
            return status
        if status >= 500:
            # A failing relay or the proxy in front of it; whatever page it sent, that is
            # what happened, not a challenge.
            raise RelayError(f"{what} answered {status} (the relay or a proxy in front of "
                             "it failed)")
        if parse_body:
            self._payload(response)      # names a challenge page before the generic error
        raise RelayError(f"{what} answered {status}")

    def _relays_404(self, response, what, error):
        """Is this 404 the relay's own answer ({"error": <error>} as JSON)? Only then is it
        final. A 404 from anything else (a hosting platform's "application not found"
        page, a proxy's page) says nothing about the job: it is a link fault, raised as a
        RelayError (ChallengeDetected for a web page) and retried with backoff."""
        if response.status_code != 404:
            return False
        payload = self._payload(response)       # a web page raises ChallengeDetected
        if payload.get('error') != error:
            raise RelayError(f"{what} answered 404 with JSON that is not the relay's "
                             f"({payload!r:.120})")
        return True

    def _request(self, method, path, *, authorized=True, **kwargs):
        # A download path carries its token: the message names the route, not the path.
        shown = '/printer/download/<token>' if path.startswith('/printer/download/') else path
        try:
            fn = self._session.post if method == 'POST' else self._session.get
            return fn(self._url(path), headers=self._headers(authorized=authorized),
                      timeout=self.timeout, **kwargs)
        except requests.RequestException as e:
            raise RelayError(f"{method} {shown} failed: {_reason(e)}") from e

    # -- protocol ----------------------------------------------------------------------

    def exchange(self, pairing_code):
        """Trade the pairing code for a signed token. None means "not yet" -- no session has
        presented this code since the relay started, or another Pi holds it."""
        response = self._request('POST', '/printer/daemon/pair', authorized=False,
                                 json={'code': pairing_code})
        self._check(response, 'pair', handled=(404,))
        if self._relays_404(response, 'pair', 'not paired'):
            return None
        token = self._payload(response).get('token')
        if not token:
            raise RelayError("pair answered 200 with no token")
        self.token = token
        return token

    def sync(self, snapshot, job_progress=None):
        """Post the status snapshot (and the daemon's word on the job it holds); return the
        job to act on, or None."""
        body = dict(snapshot)
        if job_progress is not None:
            body['job_progress'] = job_progress
        response = self._request('POST', '/printer/daemon/sync', json=body)
        if response.status_code == 401:
            raise TokenRejected("the relay rejected the token; re-pairing")
        self._check(response, 'sync')
        job = self._payload(response).get('job')
        if job is not None and not (isinstance(job, dict) and isinstance(job.get('id'), str)
                                    and job.get('id')):
            raise RelayError(f"sync answered a job of the wrong shape ({job!r:.120})")
        return job

    def ack(self, job_id, ok, error=None, *, code=None, detail=None, fields=None):
        """Report a job's outcome, with the failure's code, evidence and the figures that
        fill its sentence. False means the relay no longer holds it: final."""
        body = {'ok': bool(ok), 'error': error, 'code': code, 'detail': detail}
        if fields:
            body['fields'] = fields
        response = self._request('POST', f'/printer/daemon/jobs/{job_id}/ack', json=body)
        if response.status_code == 401:
            raise TokenRejected("the relay rejected the token; re-pairing")
        self._check(response, 'ack', handled=(404,))
        if self._relays_404(response, 'ack', 'unknown job'):
            return False
        self._payload(response)
        return True

    def start_gate(self, job_id, instance):
        """Ask the relay whether this daemon process may start the job's file now. One of
        'start', 'cancelled', 'refused' (another daemon process holds the start) or
        'unknown' (the relay no longer holds the job)."""
        response = self._request('POST', f'/printer/daemon/jobs/{job_id}/start',
                                 json={'instance': instance})
        if response.status_code == 401:
            raise TokenRejected("the relay rejected the token; re-pairing")
        self._check(response, 'start', handled=(404,))
        if self._relays_404(response, 'start', 'unknown job'):
            return 'unknown'
        outcome = self._payload(response).get('outcome')
        if outcome not in ('start', 'cancelled', 'refused'):
            raise RelayError(f"start answered an outcome of the wrong shape ({outcome!r:.60})")
        return outcome

    def ping(self):
        """Read-only health check for `penguincam-printer status`. Stores nothing on the
        relay, so it cannot disturb the running service."""
        response = self._request('GET', '/printer/daemon/ping')
        if response.status_code == 401:
            raise TokenRejected("the backend rejected the token")
        self._check(response, 'ping')
        return self._payload(response)

    def download(self, download_path, dest_path, *, size=None, sha256=None, progress=None,
                 cancelled=None):
        """Fetch the sliced file to `dest_path`. The token in the path is the whole
        authority, so no bearer header is sent. The token is never put in an error message.

        The bytes land in a sibling `.part` file that is renamed only after the last chunk
        arrives and the file matches the `size` and `sha256` the relay gave with the job:
        a connection dropped mid-stream, or a proxy that hands back the wrong bytes, leaves
        no truncated or damaged .3mf for the printer to choke on. A stall raises after the
        session's timeout with no byte. `progress(received, size)` is called per chunk;
        `cancelled()` is asked per chunk and stops the download with Cancelled."""
        response = self._request('GET', download_path, authorized=False, stream=True)
        with response:
            self._check(response, 'download', parse_body=False)
            part_path = f"{dest_path}.part"
            digest, received = hashlib.sha256(), 0
            try:
                directory = os.path.dirname(dest_path)
                if directory:
                    os.makedirs(directory, exist_ok=True)
                with open(part_path, 'wb') as fh:
                    for chunk in response.iter_content(chunk_size=64 * 1024):
                        if cancelled is not None and cancelled():
                            raise Cancelled('the delivery job was cancelled during the '
                                            'download')
                        if chunk:
                            fh.write(chunk)
                            digest.update(chunk)
                            received += len(chunk)
                            if progress is not None:
                                progress(received, size)
                if isinstance(size, int) and received != size:
                    raise DownloadCorrupt(f"the download gave {received} bytes; the relay "
                                          f"said {size}")
                if isinstance(sha256, str) and sha256 and digest.hexdigest() != sha256:
                    raise DownloadCorrupt("the download's checksum does not match the "
                                          "relay's")
                os.replace(part_path, dest_path)
            except (DownloadCorrupt, Cancelled):
                self._discard(part_path)
                raise
            except (requests.RequestException, OSError) as e:
                self._discard(part_path)
                raise RelayError(f"the download failed after {received} bytes: "
                                 f"{e.__class__.__name__}") from e

    @staticmethod
    def _discard(path):
        """Remove a half-written part file, and never mask the failure that caused it.
        (A method, not a function, so the class carries everything it uses.)"""
        try:
            os.unlink(path)
        except OSError:
            pass
