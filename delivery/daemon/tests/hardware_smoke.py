#!/usr/bin/env python3
"""Run this BY HAND against a real Bambu printer. It starts a real print.

    DELIVERY_PRINTER_IP=10.0.0.42 \
    DELIVERY_PRINTER_SERIAL=01P00A... \
    DELIVERY_PRINTER_ACCESS_CODE=<the code on the printer's screen> \
    DELIVERY_SMOKE_FILE=/path/to/a/small/sliced.gcode.3mf \
    make -C delivery hardware-smoke

It is deliberately NOT named test_*.py or *_test.py, so pytest never collects it and
`make test` never starts a print.

What it is for: the fake-printer tests are written against bambulabs_api's documented
field names. This script prints the printer's RAW status document, which becomes the
replacement for tests/fixtures/h2s_status.json -- after which the state-mapping tests are
pinned to the real thing. It also answers three open questions: the status field names and
units, the file-name form the printer reports, and how long the printer takes to report
`running` after the start command.
"""

import json
import os
import sys
import time

from penguin_delivery_daemon.printer import (
    PrinterLink, map_status, reports_file, suffixed_name,
)

WAIT_FOR_RUNNING_SECONDS = 120.0


def env(name):
    value = os.environ.get(name)
    if not value:
        sys.exit(f"set {name} in the environment (see this file's docstring)")
    return value


def main():
    ip = env('DELIVERY_PRINTER_IP')
    serial = env('DELIVERY_PRINTER_SERIAL')
    access_code = env('DELIVERY_PRINTER_ACCESS_CODE')
    source = env('DELIVERY_SMOKE_FILE')
    if not os.path.exists(source):
        sys.exit(f"{source} does not exist")

    job_id = 'j5a0ce001'
    remote_name = suffixed_name(os.path.basename(source), job_id)

    link = PrinterLink(ip, serial, access_code)
    print(f"connecting to {ip} ...")
    link.connect()
    try:
        for _ in range(40):
            if link.raw_report():
                break
            time.sleep(0.5)
        raw = link.raw_report()
        if not raw:
            sys.exit("no MQTT report arrived. Check LAN-only mode, Developer Mode and the "
                     "access code.")

        print("\n--- raw status before the print (status field names and units) ---")
        print(json.dumps(raw, indent=2, sort_keys=True, default=str))
        print("\n--- mapped snapshot ---")
        print(json.dumps(map_status(raw, printer=link.identity), indent=2, sort_keys=True))

        print(f"\nuploading as {remote_name} ...")
        print(f"upload: {link.upload(source, remote_name)}")      # judged by the listing
        print("starting the print ...")
        started = link.start(remote_name)
        print(f"start_print returned {started!r}")

        # How long from the start command to a reported `running`,
        # including the printer's preparing states.
        began = time.monotonic()
        seen = []
        while time.monotonic() - began < WAIT_FOR_RUNNING_SECONDS:
            raw = link.raw_report()
            snapshot = map_status(raw, printer=link.identity)
            marker = (snapshot['state'], raw.get('gcode_state'), raw.get('stg_cur'),
                      snapshot['file'])
            if not seen or seen[-1] != marker:
                seen.append(marker)
                print(f"  t+{time.monotonic() - began:5.1f}s  {marker}")
            if snapshot['state'] == 'running' and reports_file(snapshot, remote_name):
                print(f"\nreported running after "
                      f"{time.monotonic() - began:.1f}s")
                break
            time.sleep(1.0)
        else:
            print("\nthe printer never reported running with our file name; "
                  "check the reported file-name form below")

        final = link.raw_report()
        print("\n--- raw status while printing (this becomes the fixture) ---")
        print(json.dumps(final, indent=2, sort_keys=True, default=str))
        print("\nReported file name: "
              f"{final.get('gcode_file')!r} / subtask {final.get('subtask_name')!r}")
    finally:
        link.disconnect()


if __name__ == '__main__':
    main()
