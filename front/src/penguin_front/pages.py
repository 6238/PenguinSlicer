"""Serving the wizard's pages: `GET /` and `GET /assets/<file>` (README-details.md, "Serving
the wizard's pages"; contracts/wizard-front-server.md, "The wizard's built files").

The wizard's build leaves `index.html` and a flat `assets/` folder in `PENGUIN_WIZARD_DIST`.
`load_pages` reads them once, at start: the page with its one placeholder replaced by the
version, and every asset's bytes, so that a rebuild of the folder while the front server
runs changes nothing it serves (the front server is restarted to serve a new build, and an
open page then reloads itself for the new version). A folder without `index.html`, or an
`index.html` without the placeholder, is `PagesUnusable`, which stops the start.

Without a sign-in, `GET /` sends the browser to `/signin` with the path and query to come
back to, and an asset is `401` `front.not_signed_in`, so that no browser without a
signed-in user receives the wizard's code. Every page answer carries the contract's whole
content security policy, whose `frame-ancestors` is `'self'` on one machine and Onshape's
address alone hosted.
"""

import mimetypes
from dataclasses import dataclass
from urllib.parse import quote

from flask import Response, redirect, request

from .answers import page_file, target_path
from .context import context
from .errors import FrontError
from .identity import identity_or_none, signed_in
from .settings import SettingError

PLACEHOLDER = "__PENGUINSLICER_VERSION__"
PAGE_CACHE = "private, no-cache"
ASSET_CACHE = "private, max-age=31536000, immutable"
_POLICY = ("default-src 'self'; script-src 'self'; style-src 'self'; "
           "img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; "
           "worker-src 'self' blob:; object-src 'none'; base-uri 'none'; "
           "form-action 'self'; frame-ancestors {ancestors}")
CSP_ONE_MACHINE = _POLICY.format(ancestors="'self'")
CSP_HOSTED = _POLICY.format(ancestors="https://cad.onshape.com")
#: The kinds of the files a wizard's build makes, named here so that they do not depend on
#: the machine's own table of kinds.
_KINDS = {".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css",
          ".woff2": "font/woff2", ".woff": "font/woff", ".svg": "image/svg+xml",
          ".png": "image/png", ".json": "application/json", ".wasm": "application/wasm",
          ".map": "application/json"}


class PagesUnusable(SettingError):
    """The wizard's built folder cannot be served; the message names the folder."""

    def __init__(self, reason):
        super().__init__("PENGUIN_WIZARD_DIST", reason)


@dataclass(frozen=True)
class Pages:
    #: `index.html` with the version in place of the placeholder.
    index: bytes
    #: Each asset's name and bytes.
    assets: dict


def load_pages(folder, version):
    index_path = folder / "index.html"
    try:
        text = index_path.read_bytes().decode("utf-8")
    except OSError as exc:
        raise PagesUnusable(f"{folder} has no index.html the front server can read: "
                            f"{exc.strerror}") from None
    except UnicodeDecodeError:
        raise PagesUnusable(f"{index_path} is not UTF-8") from None
    if PLACEHOLDER not in text:
        raise PagesUnusable(f"{index_path} holds no version placeholder {PLACEHOLDER}")
    assets = {}
    folder_of_assets = folder / "assets"
    if folder_of_assets.is_dir():
        for path in sorted(folder_of_assets.iterdir()):
            if path.is_file() and not path.name.startswith("."):
                assets[path.name] = path.read_bytes()
    return Pages(text.replace(PLACEHOLDER, version).encode("utf-8"), assets)


def register(app):
    app.add_url_rule("/", "wizard_page", page, methods=["GET"])
    app.add_url_rule("/assets/<file>", "wizard_asset", asset, methods=["GET"])


def _policy():
    hosted = context()["settings"].base_url.startswith("https://")
    return CSP_HOSTED if hosted else CSP_ONE_MACHINE


def page():
    if identity_or_none() is None:
        # Bytes throughout: WSGI gives the path as Latin-1 text standing for its bytes, and
        # the query is bytes, so each byte is percent-encoded once, as it was sent.
        query = request.query_string
        back = target_path().encode("latin-1") + (b"?" + query if query else b"")
        return redirect("/signin?return=" + quote(back, safe=""), 302)
    response = Response(context()["pages"].index, 200, mimetype="text/html")
    response.headers["Content-Security-Policy"] = _policy()
    return page_file(response, PAGE_CACHE)


def asset(file):
    signed_in()
    data = context()["pages"].assets.get(file)
    if data is None:
        raise FrontError("front.no_such_request",
                         f"GET /assets/{file}: this release has no such file")
    suffix = file[file.rfind("."):] if "." in file else ""
    kind = _KINDS.get(suffix) or mimetypes.guess_type(file)[0] or "application/octet-stream"
    response = Response(data, 200, content_type=kind)
    response.headers["X-Content-Type-Options"] = "nosniff"
    return page_file(response, ASSET_CACHE)
