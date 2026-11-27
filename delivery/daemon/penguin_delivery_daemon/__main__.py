"""`python -m penguin_delivery_daemon pair | run | status | record`.

A plain Python program, started by hand, with the same commands on Windows, macOS and
Linux. Everything it keeps is in one directory, its home (`--home DIR`; the default is in
paths.py):

- `pair` finds the printer, checks it answers, writes the configuration and prints the
  pairing code to give to the print server;
- `run` is the daemon itself: it talks to the relay and to the printer until stopped;
- `status` reports on the configuration, the printer and the relay, and posts nothing,
  so it cannot disturb a running daemon;
- `record` saves every status document the printer sends, one JSON line each, so a real
  print's sequence can replace the simulated printer's invented scenarios.
"""

import argparse
import json
import os
import secrets
import signal
import sys
import time
from urllib.parse import urlparse

from penguin_delivery_daemon import VERSION
from penguin_delivery_daemon import config as cfg
from penguin_delivery_daemon import paths
from penguin_delivery_daemon.printer import PrinterLink, discover
from penguin_delivery_daemon.relay_client import ChallengeDetected, RelayClient, RelayError
from penguin_delivery_daemon.run_loop import RunLoop

# Crockford base32 without I, L, O and U. Deliberately duplicated from the relay's
# penguin_delivery_relay/relay.py: the relay is not installed beside the daemon, which never
# imports it. A test in delivery/tests pins the two literals together, so a change to one is
# caught.
ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
CODE_LENGTH = 8

CONNECT_WAIT_SECONDS = 20.0
CONNECT_POLL_SECONDS = 0.5
STATUS_WAIT_SECONDS = 10.0
DISCOVERY_SECONDS = 5.0
RECORD_POLL_SECONDS = 0.5


def resolve_paths(args):
    """Fill `args.config` and `args.download_dir` from `--home` / `--config` (paths.py)."""
    home = paths.home_for(getattr(args, 'home', None), getattr(args, 'config', None))
    if not getattr(args, 'config', None):
        args.config = home.config
    args.download_dir = home.downloads
    args.recordings = home.recordings
    # Beside the configuration, wherever that is, so it lives in the daemon's home.
    args.start_record = paths.DaemonHome(os.path.dirname(os.path.abspath(args.config))
                                         ).start_record
    return args


def generate_pairing_code():
    """Forty bits, never all digits -- an all-digit code would load out of an unquoted YAML
    value as an int."""
    while True:
        code = ''.join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))
        if not code.isdigit():
            return code


def format_pairing_code(code):
    """Display form: two groups of four separated by a dash."""
    return f"{code[:4]}-{code[4:]}"


def _connect_and_identify(link, *, wait=CONNECT_WAIT_SECONDS, clock=time.monotonic,
                          sleep=time.sleep):
    """Connect and wait for the printer's first MQTT report. Returns the snapshot, or None
    when nothing arrived before the deadline.

    The clock and the sleep are injected so the tests spend no real seconds here."""
    link.connect()
    deadline = clock() + wait
    while clock() < deadline:
        snapshot = link.snapshot()
        if snapshot.get('state') != 'unreachable':
            return snapshot
        sleep(CONNECT_POLL_SECONDS)
    return None


def _ask_until_answered(prompt, text):
    """Ask again on an empty line. Every answer `pair` asks for is required: an empty one
    would be written straight into the config file as a printer that cannot be reached."""
    while True:
        answer = prompt(text)
        if answer:
            return answer


def _choose_printer(prompt, say):
    """Ask the mentor which printer to pair with. Returns (ip, serial, model, name)."""
    try:
        found = discover(timeout=DISCOVERY_SECONDS)
    except OSError as e:
        # Binding the discovery port can fail (another listener, a container without
        # multicast). That is not a reason to stop: the typed path always works.
        say(f"Could not listen for printers ({e}); enter the address by hand.")
        found = []

    if found:
        say("Printers heard on the network:")
        for index, entry in enumerate(found, start=1):
            say(f"  {index}) {entry['model'] or 'Bambu printer'} "
                f"{entry['name'] or ''} {entry['serial']} at {entry['ip']}")
        say("Enter a number, or an IP address if your printer is not listed.")
        while True:
            answer = prompt("printer: ")
            if not answer:
                continue
            if not answer.isdigit():
                ip = answer                     # an IP address, not a menu choice
                break
            if 1 <= int(answer) <= len(found):
                chosen = found[int(answer) - 1]
                return chosen['ip'], chosen['serial'], chosen['model'], chosen['name']
            # A bare number that is not on the menu is a slip, not an address.
            say(f"There is no printer {answer} on that list.")
    else:
        say("No printers heard; enter the IP address shown on the printer's screen.")
        say("(School networks usually block the broadcast the printer uses to announce "
            "itself, so this is the normal path.)")
        ip = _ask_until_answered(prompt, "printer IP address: ")
    return ip, _ask_until_answered(prompt, "printer serial: "), None, None


def cmd_pair(args, *, ask=input, out=sys.stdout, clock=time.monotonic, sleep=time.sleep):
    """Find the printer, confirm it answers, write the config file, print the YAML lines."""
    def say(*parts):
        print(*parts, file=out)

    def prompt(text):
        """The prompt is printed rather than passed to `ask`, so a test can inject a plain
        zero-argument reader and a real run still shows the question."""
        print(text, end='', file=out, flush=True)
        return (ask() or '').strip()

    resolve_paths(args)
    backend = args.backend or cfg.DEFAULT_BACKEND_URL
    try:
        cfg.check_backend_url(backend, dev=bool(args.dev))
    except ValueError as e:
        say(f"error: {e}")
        return 2

    # dev is the permission to talk to THIS backend over plain HTTP, so it is only recorded
    # when the URL actually is plain HTTP. Writing it for an https backend would leave a
    # config that silently accepts an http one after a later hand edit.
    dev = bool(args.dev) and urlparse(backend.strip()).scheme == 'http'
    if args.dev and not dev:
        say(f"note: --dev was not needed for {backend}; not recording development mode.")

    try:
        existing = cfg.load_config(args.config)
    except (OSError, ValueError):
        # Missing is the normal case; unreadable or half-written means the old pairing code
        # is gone either way, and this run writes a whole new file over it.
        existing = None

    try:
        mqtt_port, ftps_port = parse_printer_ports(getattr(args, 'printer_ports', None))
    except ValueError as e:
        say(f"error: {e}")
        return 2
    if mqtt_port:
        # Only the simulated printer listens elsewhere; a real one is found on its network.
        ip, serial, model, name = (_ask_until_answered(prompt, "printer IP address: "),
                                   _ask_until_answered(prompt, "printer serial: "),
                                   None, None)
    else:
        ip, serial, model, name = _choose_printer(prompt, say)
    access_code = _ask_until_answered(prompt, "printer LAN access code: ")
    ports = cfg.DaemonConfig(printer_mqtt_port=mqtt_port,
                             printer_ftps_port=ftps_port).printer_ports()

    # Anything the link raises -- a mistyped address, a refused connection, bambulabs_api
    # missing from the venv -- is the same answer to the mentor as silence, and it gets the
    # same advice rather than a traceback.
    link = None
    try:
        link = PrinterLink(ip, serial, access_code, model=model, name=name, ports=ports)
        snapshot = _connect_and_identify(link, clock=clock, sleep=sleep)
    except Exception as e:
        say(f"error: could not talk to the printer at {ip}: {e}")
        snapshot = None
    finally:
        if link is not None:
            link.disconnect()
    if snapshot is None:
        say("")
        say(f"The printer at {ip} did not answer.")
        say("Check that it is in LAN-only mode with Developer Mode ON, and that the")
        say("access code matches the one on the printer's screen. Developer Mode is")
        say("required: Bambu firmware rejects print starts from third-party software")
        say("in any other mode.")
        return 1

    identity = snapshot.get('printer') or {}
    say(f"Connected to {identity.get('model') or model or 'the printer'} "
        f"{identity.get('name') or name or ''} ({serial}).")

    code = cfg.resolve_pairing_code(existing.pairing_code if existing else None,
                                    new_code=bool(args.new_code),
                                    generate=generate_pairing_code)
    config = cfg.DaemonConfig(backend_url=backend, printer_ip=ip, printer_serial=serial,
                              access_code=access_code, pairing_code=code, token='',
                              dev=dev, path=args.config, printer_mqtt_port=mqtt_port,
                              printer_ftps_port=ftps_port)
    cfg.save_config(config, path=args.config)

    say("")
    say(f"Relay:   {config.backend_url}")
    say(f"Config:  {args.config}")
    say("")
    say("Give this pairing code to your team's print server, where it asks for the")
    say("printer's pairing code (for a team configuration file, these two lines):")
    say("")
    say("printing:")
    say(f'  pairing_code: "{format_pairing_code(code)}"')
    say("")
    home = ['--home', os.path.dirname(os.path.abspath(args.config))]
    say("Then start the daemon and leave it running:")
    say(f"  python -m penguin_delivery_daemon run {' '.join(home)}")
    return 0


def parse_printer_ports(text):
    """`--printer-ports MQTT,FTPS` -> (mqtt, ftps); None or empty -> (0, 0), the printer's
    own. For the simulated printer only (see "Try it on one machine" in README-details.md)."""
    if not text:
        return 0, 0
    parts = [part.strip() for part in str(text).split(',')]
    if len(parts) != 2 or not all(part.isdigit() and 0 < int(part) < 65536
                                  for part in parts):
        raise ValueError(f"--printer-ports takes two port numbers, MQTT,FTPS (got {text!r})")
    return int(parts[0]), int(parts[1])


def is_pairing_code(value):
    """True for the eight symbols `pair` writes. Anything else -- an empty field, a
    hand-edited YAML paste with its dash still in it, a truncated line -- is not a code the
    relay could ever recognise."""
    return (isinstance(value, str) and len(value) == CODE_LENGTH
            and all(ch in ALPHABET for ch in value))


def wait_for_paired_config(path, *, log=print, sleep=time.sleep, clock=time.monotonic,
                           interval=5.0, log_every=60.0):
    """Block until the config file is there AND carries a usable pairing code.

    A config with no code cannot pair, so starting the loop on one would only fill the
    log with exchanges the backend answers 404. Waiting beats exiting for the same reason
    wait_for_config waits: whoever started it sees the one message a mentor needs. Logs
    once at the start and then once a minute."""
    started = clock()
    last_log = None
    while True:
        config = cfg.wait_for_config(path, log=log, sleep=sleep, clock=clock,
                                     interval=interval, log_every=log_every)
        if is_pairing_code(config.pairing_code):
            return config
        now = clock()
        if last_log is None or now - last_log >= log_every:
            log(f"{path} has no pairing code -- run `{cfg.PAIR_COMMAND}` first "
                f"(waited {int(now - started)}s)")
            last_log = now
        sleep(interval)


def _ensure_download_dir(path):
    """Make the scratch directory, readable only by the service user."""
    os.makedirs(path, mode=0o700, exist_ok=True)
    try:
        # A directory left behind by an older install may be looser than makedirs would
        # have made it; exist_ok does not touch the mode of one that is already there.
        os.chmod(path, 0o700)
    except OSError:
        pass
    return path


class _InterruptOnce:
    """A SIGINT handler: the first interrupt stops the daemon (KeyboardInterrupt); every
    later one is ignored, so several Ctrl-C at once (to the program and to whatever started
    it) cannot break into the lines that stop it and end the log in a traceback."""

    def __init__(self):
        self.seen = 0
        self.previous = None
        self.installed = False

    def __call__(self, signum, frame):
        self.seen += 1
        if self.seen == 1:
            raise KeyboardInterrupt

    def install(self):
        try:
            self.previous = signal.signal(signal.SIGINT, self)
            self.installed = True
        except ValueError:
            pass                    # not the main thread: interrupts are not ours to take

    def uninstall(self):
        """Put the earlier handler back; after a real interrupt keep ignoring them, so the
        last moments before the process exits stay quiet too."""
        if self.installed:
            signal.signal(signal.SIGINT, signal.SIG_IGN if self.seen else self.previous)


def cmd_run(args, *, out=sys.stdout, download_dir=None, clock=time.monotonic,
            sleep=time.sleep):
    """The daemon. Waits for the config file rather than exiting."""
    interrupts = _InterruptOnce()
    interrupts.install()
    try:
        return _run(args, out=out, download_dir=download_dir, clock=clock, sleep=sleep)
    finally:
        interrupts.uninstall()


def _run(args, *, out, download_dir, clock, sleep):
    def log(*parts):
        print(*parts, file=out, flush=True)

    resolve_paths(args)
    download_dir = download_dir or args.download_dir
    try:
        config = wait_for_paired_config(args.config, log=log, clock=clock, sleep=sleep)
    except KeyboardInterrupt:
        # Ctrl-C while waiting, from a mentor running this by hand: not a crash.
        log("stopping")
        return 0
    # Refuse a backend URL the daemon must not talk to before anything is opened. This is
    # the same check preflight() makes; only preflight logs the development warning, so
    # asking here costs no duplicate line.
    try:
        cfg.check_backend_url(config.backend_url, dev=config.dev)
    except ValueError as e:
        log(f"error: {e}")
        return 2

    printer = PrinterLink(config.printer_ip, config.printer_serial, config.access_code,
                          log=log, ports=config.printer_ports())
    relay = RelayClient(config.backend_url, token=config.token or None)
    loop = RunLoop(config, relay, printer, log=log,
                   download_dir=_ensure_download_dir(download_dir),
                   start_record_path=args.start_record)
    log(f"penguincam-printer {VERSION} running against {config.backend_url}; "
        f"printer at {config.printer_ip}; files in {os.path.dirname(args.config)}")
    status = 0
    try:
        printer.connect()
        loop.run_forever()
    except ValueError as e:
        # Backstop: run_forever() calls preflight(), which makes the same check again.
        log(f"error: {e}")
        status = 2
    except KeyboardInterrupt:
        log("stopping")
    except Exception as e:
        # A connect that throws -- no bambulabs_api in the venv, a socket the daemon's
        # computer cannot open -- is a message and an exit code, not a traceback in the log.
        log(f"error: could not start: {e}")
        status = 1
    finally:
        # Ends the job thread's waits at once; its file is never started after this.
        loop.stop()
        loop.executor.shutdown(wait=True)
        printer.disconnect()
    return status


def cmd_status(args, *, out=sys.stdout, clock=time.monotonic, sleep=time.sleep):
    """What a mentor runs when the wizard says offline. Posts no snapshot, so it cannot
    disturb the running service."""
    def say(*parts):
        print(*parts, file=out)

    resolve_paths(args)
    try:
        config = cfg.load_config(args.config)
    except FileNotFoundError:
        say(f"No config file at {args.config}. Run `python -m penguin_delivery_daemon "
            "pair` first.")
        return 1
    except (OSError, ValueError) as e:
        say(f"The config file at {args.config} cannot be read ({e.__class__.__name__}: "
            f"{str(e).splitlines()[0] if str(e) else ''}). Run pair again to write a new "
            "one.")
        return 1

    say(f"penguincam-printer {VERSION}")
    say(f"backend: {config.backend_url}")
    say(f"printer IP: {config.printer_ip}")
    say(f"serial: {config.printer_serial}")
    code = format_pairing_code(config.pairing_code) if config.pairing_code else '(none)'
    say(f"pairing code: {code}")
    # The token itself is a secret and is never printed, here or anywhere else.
    say(f"token: {'set' if config.token else 'not set'}")
    say(f"dev mode: {'yes' if config.dev else 'no'}")

    printer = PrinterLink(config.printer_ip, config.printer_serial, config.access_code,
                          ports=config.printer_ports())
    try:
        snapshot = _connect_and_identify(printer, wait=STATUS_WAIT_SECONDS, clock=clock,
                                         sleep=sleep)
    except Exception as e:
        snapshot = None
        say(f"printer: could not connect ({e})")
    finally:
        printer.disconnect()
    if snapshot is not None:
        say(f"printer: answering, state {snapshot.get('state')}")
    else:
        say("printer: no MQTT report -- check LAN-only mode, Developer Mode and the "
            "access code")

    relay = RelayClient(config.backend_url, token=config.token or None)
    try:
        flags = relay.ping()
        say(f"backend: reachable, waiting={flags.get('waiting')} "
            f"online={flags.get('online')}")
    except ChallengeDetected as e:
        say(f"backend: blocked by a bot challenge -- {e}")
    except RelayError as e:
        say(f"backend: not reachable ({e})")
    return 0


def cmd_record(args, *, out=sys.stdout, clock=time.monotonic, sleep=time.sleep,
               link=None):
    """Save every status document the printer sends, one JSON line each, until Ctrl-C or
    `--seconds` have passed. For capturing a real print's sequence in one session at the
    printer, to replace the simulated printer's invented scenarios. The access code is
    never written."""
    def say(*parts):
        print(*parts, file=out, flush=True)

    resolve_paths(args)
    try:
        config = cfg.load_config(args.config)
    except (OSError, ValueError) as e:
        say(f"No usable config file at {args.config} ({e.__class__.__name__}); run pair "
            "first.")
        return 1
    target = args.out or os.path.join(
        args.recordings, time.strftime('status-%Y%m%d-%H%M%S.jsonl'))
    directory = os.path.dirname(os.path.abspath(target))
    os.makedirs(directory, exist_ok=True)
    link = link or PrinterLink(config.printer_ip, config.printer_serial, config.access_code,
                               log=say, ports=config.printer_ports())
    started = clock()
    saved, last = 0, None
    say(f"recording the printer's status documents to {target}; press Ctrl-C to stop")
    try:
        link.connect()
        with open(target, 'a', encoding='utf-8') as fh:
            while args.seconds is None or clock() - started < args.seconds:
                report = link.raw_report()
                if report and report != last:
                    last = report
                    fh.write(json.dumps({'t': round(clock() - started, 2), 'print': report},
                                        sort_keys=True) + '\n')
                    fh.flush()
                    saved += 1
                sleep(RECORD_POLL_SECONDS)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        say(f"error: could not record: {e}")
        return 1
    finally:
        link.disconnect()
    say(f"saved {saved} status documents to {target}")
    return 0


def _common(parser):
    parser.add_argument('--home', default=None,
                        help='the directory for the configuration, state and downloads '
                             f'(default {paths.default_home()})')
    parser.add_argument('--config', default=None,
                        help='the configuration file itself, instead of --home')


def build_parser():
    parser = argparse.ArgumentParser(prog='python -m penguin_delivery_daemon',
                                     description='Printer delivery daemon')
    # --home and --config are declared on each subcommand, not here: a top-level copy
    # would shadow the subparser's value with its own default.
    sub = parser.add_subparsers(dest='command', required=False)

    pair = sub.add_parser('pair', help='find the printer and mint a pairing code')
    _common(pair)
    pair.add_argument('--new-code', action='store_true',
                      help='mint a fresh pairing code instead of keeping the existing one')
    pair.add_argument('--backend', default=None,
                      help='relay URL (defaults to the hosted service)')
    pair.add_argument('--dev', action='store_true',
                      help='allow a plain-HTTP relay URL (development only)')
    pair.add_argument('--printer-ports', default=None, metavar='MQTT,FTPS',
                      help="the printer's MQTT and FTPS ports, for the simulated printer "
                           "only (a real printer uses its own)")

    run = sub.add_parser('run', help='run the daemon until stopped')
    _common(run)

    status = sub.add_parser('status', help='report on the config, printer and relay')
    _common(status)

    record = sub.add_parser('record', help="save every status document the printer sends")
    _common(record)
    record.add_argument('--out', default=None, help='the file to append to')
    record.add_argument('--seconds', type=float, default=None,
                        help='stop after this many seconds (default: at Ctrl-C)')
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    commands = {'pair': cmd_pair, 'run': cmd_run, 'status': cmd_status,
                'record': cmd_record}
    if args.command in commands:
        return commands[args.command](args)
    parser.print_help()
    return 1


if __name__ == '__main__':
    sys.exit(main())
