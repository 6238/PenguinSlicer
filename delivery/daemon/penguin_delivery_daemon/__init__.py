"""Printer delivery's daemon: a plain Python program, started by hand on the daemon's
computer, on the printer's network (Windows, macOS or Linux), that takes jobs from the
relay and starts them on one Bambu Lab printer.

It runs with `python -m penguin_delivery_daemon`; `pyproject.toml` beside it makes it
installable as a package as well. The relay never imports this package, and this package
never imports the relay; the only thing they share is the HTTP protocol in relay_client.py.

The `penguincam-printer` command and the User-Agent keep the original daemon's name.
"""

VERSION = "1.0.0"
USER_AGENT = f"penguincam-printer/{VERSION}"
