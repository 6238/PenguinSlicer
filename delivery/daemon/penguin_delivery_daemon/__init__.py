"""Printer delivery's daemon: a small always-on process for a Raspberry Pi on the shop LAN
that takes jobs from the relay and starts them on one Bambu Lab printer.

The installer copies this directory onto the Pi and runs it with
`python -m penguin_delivery_daemon`; `pyproject.toml` beside it makes it installable as a
package as well. The relay never imports this package, and this package never imports the
relay; the only thing they share is the HTTP protocol in relay_client.py.

The installed names on a Pi (the `penguincam-printer` command and service, the `penguincam`
user, /etc/penguincam-printer) and the User-Agent are kept from the original daemon, so a
Pi already in a shop keeps working after an upgrade.
"""

VERSION = "1.0.0"
USER_AGENT = f"penguincam-printer/{VERSION}"
