"""The relay as a Flask application of its own.

    app = create_app(secret_key=..., identify=..., find_sliced_file=...)

The caller either runs this app on its own, or mounts it beside its own app (for example
with werkzeug's DispatcherMiddleware) so that /printer/* reaches it. The caller's functions
are described in caller.py; everything else has a default.
"""

import time

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from .limits import RateLimiter
from .relay import PrinterRelay
from .routes import RelayContext, register_routes
from .sliced_files import SlicedFileStore

EXTENSION = 'penguin_delivery_relay'


def create_app(*, secret_key, identify, find_sliced_file, clock=time.time, log=None,
               on_event=None, dev=False, dev_pairing_code=None, trusted_proxy_hops=1,
               installer_path=None, spool_dir=None):
    """Build the relay's application.

    secret_key        Signs the daemon's token. Must be the same across restarts: a new key
                      makes every daemon re-pair, and a daemon can only re-pair after the
                      caller has presented its code again.
    identify          `identify(request) -> Team | None`; see caller.py.
    find_sliced_file  `find_sliced_file(token, team) -> SlicedFile | None`; see caller.py.
    clock             Wall-clock seconds. Every age, deadline and rate-limit window of the
                      relay is measured on it.
    log               `log(text)` for the relay's log lines. None logs nothing.
    on_event          `on_event(kind, team_number=..., user=..., metadata={...})` for each
                      job sent (`printer_send`) and each job finished or expired
                      (`printer_ack`). None drops them.
    dev               Development mode: the daemon routes accept plain HTTP, and
                      dev_pairing_code is honoured. Never set it in production.
    dev_pairing_code  A pairing code to treat as presented, so a daemon can pair before any
                      caller has used the relay. Ignored unless dev is set.
    trusted_proxy_hops  How many proxies in front of the relay to trust for the client's
                      address, scheme and host (werkzeug's ProxyFix). 0 trusts none.
    installer_path    The daemon's install.sh, served at /install-printer.sh. None leaves the
                      route out.
    spool_dir         Where the relay keeps its copy of a sliced file that arrived as a
                      stream. None makes a private temporary directory on first use.
    """
    app = Flask(__name__)
    relay = PrinterRelay(clock=clock)
    ctx = RelayContext(relay=relay, files=SlicedFileStore(spool_dir),
                       limiter=RateLimiter(clock), secret_key=secret_key,
                       identify=identify, find_sliced_file=find_sliced_file, clock=clock,
                       log=log, on_event=on_event, dev=bool(dev),
                       dev_pairing_code=dev_pairing_code, installer_path=installer_path)
    app.extensions[EXTENSION] = ctx
    register_routes(app, ctx)
    if trusted_proxy_hops:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=trusted_proxy_hops,
                                x_proto=trusted_proxy_hops, x_host=trusted_proxy_hops)
    return app


def relay_of(app):
    """The relay state behind an app made by create_app: `.relay` is the PrinterRelay, so a
    caller can call `relay_of(app).relay.note_code(code)` when a team's code first reaches it
    (on sign-in, say), before any status poll."""
    return app.extensions[EXTENSION]
