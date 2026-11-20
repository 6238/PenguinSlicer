# Scenarios for the simulated printer

Each file scripts one run of the simulated printer (`../printer.py`). Every sequence here
is **invented**: only one real status document of the H2S has been recorded (its fields
are in `daemon/tests/fixtures/h2s_status.json`, `running_as_reported_by_h2s`), and the
rest follows the first hardware test's notes and what the printer library reads.

| Key | Meaning |
|---|---|
| `description` | What the scenario plays, and what in it is invented |
| `base` | Another scenario this one changes; only the keys given here differ |
| `idle` | The status document before any print |
| `upload` | How the FTPS server answers a `STOR`: `{}` stores it and answers 226; `reply` another final line (the 426 case); `short_by` keeps that many bytes fewer; `cut_bytes` drops the connection after that many bytes and answers 426; `refuse` answers 550 |
| `start` | `accept` (the default) starts the uploaded file; `ignore` does nothing |
| `tls` | `1.2` (the default) caps both servers at TLS 1.2; `1.3` makes them speak only TLS 1.3 |
| `pushall` | `answer` (the default) answers the library's `pushall` with the whole status; `ignore` says nothing, as a printer whose stream went quiet (a test can also switch it with `answer_pushall`) |
| `print` | The status documents sent once the print starts, one per `step()`. Each is merged into the last, as the printer's own updates are. `{subtask}` is the uploaded name without `.gcode.3mf`, `{file}` the whole name, `{other}` the scenario's `other_subtask` |
| `recording` | A file written by `python -m penguin_delivery_daemon record`, beside these; its documents become the `print` steps |

## Replacing an invented sequence with a real one

1. At the printer, start `python -m penguin_delivery_daemon record --home <home>` and
   send a print (or start one on the printer's screen). Stop it with Ctrl-C after the
   print ends. It writes `recordings/status-<date>.jsonl` in the daemon's home.
2. Copy that file here, and in the scenario put `"recording": "<that file name>"`. The
   documents of the recording replace the scenario's `print` steps. The first document
   that names the print is where the start was answered; cut what came before it.
3. Run `make -C delivery test-sim`. Where the daemon reads the real sequence differently
   from the invented one, the test that fails names the difference.
