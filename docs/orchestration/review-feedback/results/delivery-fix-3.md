# Fixes for review 3 of printer delivery

Written Fri 2026-11-20 11:58 PT, working from [delivery-review-3.md](delivery-review-3.md)
under [fix.md](../briefs/fix.md) and [standing-rules.md](../briefs/standing-rules.md).
Only `delivery/` was changed; nothing is committed.

## Defect 1: "it answered" when the printer gave no answer — fixed

- `PrinterLink.delete` (`daemon/penguin_delivery_daemon/printer.py`) now tells a reply from
  the printer (three digits first, `is_printer_reply`) from the error that ended a delete
  the printer never answered. The library logs only `str(e)`, so the text decides: a
  timeout or a reset becomes `no answer: timed out` / `no answer: [Errno 104] ...`, and
  ftplib's empty `EOFError` (a dropped connection) becomes `no answer: the connection
  dropped`. A refused connection or failed login stays `no connection: ...`; no log line at
  all stays `no answer`. Outcomes are unchanged (all `UNCONFIRMED`).
- `RunLoop._remove_from_printer` writes "(it answered: <reply>)" only for a reply, and
  otherwise "(<what happened>)", e.g. "could not confirm that X was removed from the
  printer (no answer: timed out)".
- Tests, each seen failing first: `test_any_other_answer_is_a_delete_that_could_not_be_confirmed`
  (timeout and reset cases), `test_a_connection_dropped_during_the_delete_is_said_so`,
  `test_only_a_three_digit_reply_is_the_printers_answer` (`tests/test_daemon_printer.py`);
  `test_a_delete_with_no_answer_from_the_printer_does_not_say_it_answered` (four cases,
  `tests/test_daemon_job_flow.py`); the upstream check
  `test_a_delete_returns_the_reply_or_logs_and_swallows_the_printers_answer` now also
  drives the real library and ftplib with a socket timeout and an `EOFError`.
- The guide's step 5 says what the warning shows in each case.
- Choice: a non-numeric line from the printer (ftplib's `error_proto`, e.g. "hello") cannot
  be told from an error's text, so it reads as "no answer: hello". It is a contrived case
  and the outcome is the same warning.

## Defect 2: two names for one computer — fixed

The name is **the daemon's computer** throughout `delivery/`. The guide defines it once, at
first mention (README line 8): "the daemon's computer (the computer next to the printer, on
the printer's network, that runs the daemon)". Changed: every student sentence and remedy
in `relay/penguin_delivery_relay/errors.py` and their matching rules, the two relay
refusal texts in `relay.py` (and its docstring), the two stage labels in `deliveries.py`,
comments and docstrings in `__init__.py`, `__main__.py`, `config.py`, `printer.py`,
`relay_client.py`, `run_loop.py`, `start_record.py`, `daemon/pyproject.toml`,
`scripts/upgrade_printer_library.py`, and the tests asserting those texts.

Of the same kind, beside it, also fixed: a third name, "the printer computer", in nine
remedies in `errors.py`; "the computer next to it" / "next to its printer" in `relay.py`;
"a shop computer" in `daemon/tests/test_daemon_package.py`. A search of `delivery/` for
"computer next to the printer" finds only the definition.

## Coordinator's added item: the two limits that wait for the real printer — done

README, "Two limits that wait for the real printer": it now says the timed rule is the
rule and stays as built, keeps both limits and what the session at the real printer
measures, and mentions the rule needing no timing in one sentence, as what would be
considered only if the measurements show the H2S slow to show a print or keeping an old
end. "The owner's choice" and "until the owner decides" are gone. No code changed.

## Suites

- Fast suite, 20 runs, random order (`--randomly-seed` 31337 + 7919 × run), 2 workers:
  **20 of 20 passed**, 1,123 tests and 180 subtests each, 3.51 s to 4.28 s. Script and logs:
  `/tmp/claude-1000/-repos-popcornpenguins/866ece9c-6c1b-4561-aa91-d02b79810b96/scratchpad/delivery-fix-3/repeat.sh`
  and `repeat-*.log` beside it.
- `make test-properties`: 3 passed, 5.27 s. `make test-sim`: 37 passed, 16.3 s.
  `make test-upstream`: 57 passed, 16.7 s.
- `make coverage`: every module as in review 3 (`run_loop.py` 99%, `printer.py` 97%,
  `errors.py` 100%, `relay.py` 99%, `deliveries.py` 98%); coverage has not fallen.

Every pytest run was bounded by `timeout -k 5` and a 4 GB address-space limit.
