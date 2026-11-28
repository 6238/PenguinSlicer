"""The watch for secrets: no log line and no answer of the front server, in any test of the
fast suite, holds a secret the test used (README-details.md, "The log", its tests).

Each test gets a fresh `Watch` (`current`), filled by the guards in conftest.py:

- **secrets:** every cookie key the front server is given or makes (its text, and for bytes
  made at start their hexadecimal and base64 forms), every cookie it seals, and every token
  the stand-in for Onshape issues;
- **texts:** every line the log writes, prints or gathers, every line a test's stand-in for
  the log is given, and every answer of the front server: its headers (all but the
  `Set-Cookie` that carries the cookie by design) and its body when it is held whole.

After the test, a secret found in a text fails it, naming where."""

import base64
import json

#: A secret shorter than this is not searched for: it could match by chance.
SHORTEST = 8


class Watch:
    def __init__(self):
        self.secrets = set()
        self.texts = []

    def secret(self, value):
        """Note a secret, in each form it could be written."""
        if isinstance(value, (bytes, bytearray)):
            raw = bytes(value)
            forms = {raw.hex(), base64.b64encode(raw).decode(),
                     base64.urlsafe_b64encode(raw).decode().rstrip("="),
                     base64.b64encode(raw).decode().rstrip("=")}
            try:
                forms.add(raw.decode())
            except UnicodeDecodeError:
                pass
        else:
            forms = {str(value)}
        self.secrets.update(form for form in forms if len(form) >= SHORTEST)

    def text(self, where, text):
        self.texts.append((where, text if isinstance(text, str) else
                           json.dumps(text, default=str)))

    def leaks(self):
        """(where, the secret's first characters) for each secret found in a text."""
        return [(where, secret[:6] + "…") for where, text in self.texts
                for secret in self.secrets if secret in text]


current = Watch()
