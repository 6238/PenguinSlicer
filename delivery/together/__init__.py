"""The relay and the daemon run together on one machine, with the printer played by a
stand-in. `python -m together` (or `make together`) is the one command; the tests in
delivery/tests drive the same pieces without a socket.

This folder belongs to neither half: it imports both, which neither half may do.
"""
