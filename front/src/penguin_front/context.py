"""What every request's code reaches through the application: the settings, the clock, the
log, the version, the cookie key, the state bucket, the client for the slice service and the
page files, kept in the application's extensions under `EXTENSION`."""

from flask import current_app

EXTENSION = "penguin_front"


def context():
    return current_app.extensions[EXTENSION]
