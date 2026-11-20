"""`python -m simulator`: the simulated printer on its own, for a daemon run by hand.

    python -m simulator --scenario whole_print --mqtt-port 18883 --ftps-port 18990

It listens on 127.0.0.1 only, prints the serial and access code a hand-run `pair` asks for,
and plays the scenario's print one status document every `--step-seconds` once a start
command has arrived, so a hand-run daemon sees a whole print go by. Every login, file,
command and status document is printed. Ctrl-C stops it. See the guide's "Try it on one
machine"; the suites drive the same class step by step instead (simulator/printer.py).
"""

import argparse
import sys
import threading
import time

from simulator.printer import SimulatedPrinter, scenario_names


def run(scenario, *, mqtt_port, ftps_port, step_seconds, out=sys.stdout, stop=None,
        ready=None):
    """Serve until `stop` is set (or Ctrl-C). `ready(printer)` is called once listening."""
    stop = stop or threading.Event()

    def say(text):
        print(f"{time.strftime('%H:%M:%S')}  {text}", file=out, flush=True)

    printer = SimulatedPrinter(scenario)
    printer.start(mqtt_port=mqtt_port, ftps_port=ftps_port)
    say(f"simulated printer, scenario {scenario}, on 127.0.0.1: MQTT {printer.mqtt_port}, "
        f"FTPS {printer.ftps_port}")
    say(f"serial {printer.serial}, access code {printer.access_code} (a test value)")
    say("pair the daemon with: python -m penguin_delivery_daemon pair --printer-ports "
        f"{printer.mqtt_port},{printer.ftps_port} ... (IP 127.0.0.1)")
    if ready is not None:
        ready(printer)
    seen = {'logins': 0, 'files': set(), 'commands': 0, 'published': 0}

    def tell():
        """Print what happened since the last call."""
        for protocol, accepted in printer.logins[seen['logins']:]:
            say(f"{protocol} login {'accepted' if accepted else 'refused'}")
        seen['logins'] = len(printer.logins)
        for name in sorted(set(printer.files) - seen['files']):
            say(f"received {name} ({len(printer.files[name])} bytes)")
        seen['files'] = set(printer.files)
        for command in printer.commands[seen['commands']:]:
            say(f"command: {command.get('command')} {command.get('file') or ''}".rstrip())
        seen['commands'] = len(printer.commands)
        for document in printer.published[seen['published']:]:
            say(f"status: {document}")
        seen['published'] = len(printer.published)

    playing_since = None
    try:
        while not stop.wait(0.2):
            tell()
            if printer.steps and playing_since is None:
                playing_since = time.monotonic()
            if playing_since is not None and time.monotonic() - playing_since >= step_seconds:
                playing_since = time.monotonic() if printer.step() else None
    except KeyboardInterrupt:
        pass
    finally:
        printer.stop()
        tell()
        say("stopped")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -m simulator', description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--scenario', default='whole_print', choices=scenario_names(),
                        help='the scenario file in simulator/scenarios (default whole_print)')
    parser.add_argument('--mqtt-port', type=int, default=18883,
                        help='the MQTT port on 127.0.0.1 (default 18883; 0 lets the system '
                             'pick)')
    parser.add_argument('--ftps-port', type=int, default=18990,
                        help='the FTPS port on 127.0.0.1 (default 18990; 0 lets the system '
                             'pick)')
    parser.add_argument('--step-seconds', type=float, default=3.0,
                        help='seconds between the status documents of the print (default 3)')
    args = parser.parse_args(argv)
    return run(args.scenario, mqtt_port=args.mqtt_port, ftps_port=args.ftps_port,
               step_seconds=args.step_seconds)


if __name__ == '__main__':
    sys.exit(main())
