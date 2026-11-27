"""The stand-in for Onshape: its OAuth approval and token exchange, and the two calls of a
sign-in (who the user is, and their companies and classrooms), served on the loopback
address. It counts every call to Onshape's interface (`calls`), since each one counts
against the Onshape app's yearly allowance.

The shapes are those of Onshape's public documentation as the guide reads it: the token
answer of OAuth 2, `GET /api/users/sessioninfo` giving the user's `id` and `name`, and
`GET /api/companies` giving `items`, each with `id` and `name`. What Onshape really answers,
above all for an account with no company or classroom, is seen only in phase 3
(README-details.md, "Signing in"), and this stand-in is corrected then.
"""

import secrets
from urllib.parse import urlencode

from flask import Flask, jsonify, redirect, request

from front_fakes import LoopbackServer


class OnshapeStandIn:
    def __init__(self):
        self.user = {"id": "5f1e0c2a9b3d4e6f7a8b9c0d", "name": "Pat Example"}
        self.companies = [{"id": "c0ffee0000000000000000aa", "name": "Example Robotics"}]
        self.refuse_approval = False
        self.refuse_codes = False
        #: Each call to Onshape's interface, as (method, path), in the order received.
        self.calls = []
        self._codes = set()
        self._access = set()
        self._refresh = set()
        self.app = self._make_app()
        self._server = LoopbackServer(self.app)

    def start(self):
        return self._server.start()

    @property
    def url(self):
        return self._server.url

    def stop(self):
        self._server.stop()

    def unreachable(self):
        self.stop()

    def reachable(self):
        self.start()

    def _tokens(self):
        access, refresh = secrets.token_urlsafe(16), secrets.token_urlsafe(16)
        self._access.add(access)
        self._refresh.add(refresh)
        return jsonify(access_token=access, refresh_token=refresh, expires_in=3600,
                       token_type="Bearer")

    def _make_app(self):
        app = Flask("onshape_standin", static_folder=None)
        standin = self

        @app.get("/oauth/authorize")
        def authorize():
            back = {"state": request.args.get("state", "")}
            if standin.refuse_approval:
                back = {"error": "access_denied", **back}
            else:
                code = secrets.token_urlsafe(12)
                standin._codes.add(code)
                back = {"code": code, **back}
            return redirect(f"{request.args.get('redirect_uri', '')}?{urlencode(back)}")

        @app.post("/oauth/token")
        def token():
            form = request.form
            if form.get("grant_type") == "refresh_token":
                if form.get("refresh_token") not in standin._refresh:
                    return jsonify(error="invalid_grant"), 400
                standin._refresh.discard(form["refresh_token"])
                return standin._tokens()
            code = form.get("code")
            if standin.refuse_codes or code not in standin._codes:
                return jsonify(error="invalid_grant"), 400
            standin._codes.discard(code)
            return standin._tokens()

        def signed(answer):
            standin.calls.append((request.method, request.path))
            bearer = request.headers.get("Authorization", "")
            if not bearer.startswith("Bearer ") or bearer[7:] not in standin._access:
                return jsonify(message="Unauthorized"), 401
            return jsonify(answer())

        app.add_url_rule("/api/users/sessioninfo", "sessioninfo",
                         lambda: signed(lambda: standin.user))
        app.add_url_rule("/api/companies", "companies",
                         lambda: signed(lambda: {"items": standin.companies}))
        return app
