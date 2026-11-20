"""A `requests`-shaped session that answers from a Flask app's test client.

The daemon's RelayClient takes a `session` with `.post` and `.get`; this one hands those
calls to the relay app in the same process, so the real client talks to the real relay
with no socket at all. The response offers what RelayClient reads: status_code, headers,
text, json(), iter_content(), close() and the context-manager protocol.
"""

import json as json_module
from urllib.parse import urlsplit


class InProcessResponse:
    def __init__(self, response):
        self._response = response
        self.status_code = response.status_code
        self.headers = response.headers
        self._data = response.get_data()
        self.closed = False

    @property
    def text(self):
        return self._data.decode('utf-8', 'replace')

    def json(self):
        return json_module.loads(self.text)        # a ValueError when it is not JSON

    def iter_content(self, chunk_size=8192):
        for start in range(0, len(self._data), chunk_size):
            yield self._data[start:start + chunk_size]

    def close(self):
        self.closed = True
        self._response.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


class InProcessSession:
    """Routes every request to `app`. The scheme and host of the URL become the test
    client's base URL, so `https://relay.test` arrives as a secure request."""

    def __init__(self, app):
        self._client = app.test_client()
        self.calls = []

    def _send(self, method, url, headers=None, json=None, **_ignored):
        parts = urlsplit(url)
        path = parts.path + (f'?{parts.query}' if parts.query else '')
        self.calls.append((method, path))
        response = self._client.open(path, method=method, headers=headers or {},
                                     json=json, base_url=f'{parts.scheme}://{parts.netloc}')
        return InProcessResponse(response)

    def post(self, url, **kwargs):
        return self._send('POST', url, **kwargs)

    def get(self, url, **kwargs):
        return self._send('GET', url, **kwargs)
