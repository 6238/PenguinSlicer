"""`python -m together.relay_server`: the relay on its own, for trying printer delivery by
hand on one machine.

    python -m together.relay_server --code 7K3M-Q9XW --port 8787

It serves the relay in development mode (plain HTTP) on 127.0.0.1 only, with a stand-in
caller: every request is the one team whose pairing code is `--code` (the code a hand-run
`pair` printed), and the send token `sample` names the sliced file `--file` (the
placeholder sample by default). Its log lines, the relay's structured lines included, go
to the terminal. A fresh secret key is made at each start, so a daemon paired against an
earlier run pairs again by itself. Ctrl-C stops it. Never use it for a real shop: it
signs in everyone as one team. See "Try it on one machine" in delivery/README-details.md.
"""

import argparse
import os
import secrets
import sys
import time

from werkzeug.serving import make_server

from penguin_delivery_relay import SlicedFile, Team, create_app

from together.__main__ import SAMPLE, SEND_TOKEN, QuietRequestHandler


def build(code, sliced_path, *, out=sys.stdout):
    team = Team(pairing_code=code, team_number=None, user='by-hand')
    sliced = SlicedFile(filename=os.path.basename(sliced_path), path=sliced_path)

    def log(*parts):
        print(f"{time.strftime('%H:%M:%S')}  {' '.join(str(p) for p in parts)}", file=out,
              flush=True)

    app = create_app(secret_key=secrets.token_hex(16), identify=lambda request: team,
                     find_sliced_file=lambda token, team: sliced if token == SEND_TOKEN
                     else None,
                     log=log, dev=True, dev_pairing_code=code, trusted_proxy_hops=0)
    return app, log


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -m together.relay_server',
                                     description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--code', required=True,
                        help='the pairing code `pair` printed, for example 7K3M-Q9XW')
    parser.add_argument('--port', type=int, default=8787,
                        help='the port on 127.0.0.1 (default 8787)')
    parser.add_argument('--file', default=SAMPLE,
                        help='the sliced file the send token `sample` names')
    args = parser.parse_args(argv)
    app, log = build(args.code, os.path.abspath(args.file))
    server = make_server('127.0.0.1', args.port, app, threaded=True,
                         request_handler=QuietRequestHandler)
    log(f"relay listening at http://127.0.0.1:{server.server_port} (development mode, "
        "one stand-in team); Ctrl-C stops it")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        log("stopped")
    return 0


if __name__ == '__main__':
    sys.exit(main())
