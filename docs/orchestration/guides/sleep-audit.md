# Audit of waits on the wall clock in the tests

Made Fri 2026-11-27 for the work item of phase 5 in
[the plan](../../plans/penguin-slicer-plan.md#phase-5-the-real-printer): printer
delivery's tests that wait on the wall clock are rewritten to use a fake clock and fakes
that put network events in an exact order. No test code was changed.

**Searched:** every Python file under `delivery/` (its `conftest.py`, `daemon/tests/`,
`relay/tests/`, `simulator/tests/` and `tests/`) and under `slice/tests/`, for `sleep`,
`.wait(`, `join(`, `timeout=`, `time.monotonic`, `time.time`, `Event()`, `Barrier` and the
helpers that poll (`wait_until`, `wait_for`, `drive`). Each hit was opened.

**Terms used here.** A **real wait** is a test whose outcome depends on time passing on
the wall clock: the test, the code under test or upstream code it drives sleeps or waits a
duration. A **stand-in** is a wait the test controls: a sleep injected as a fake clock's
step, or a wait on an event (a thread's end, a condition, a lock, a signal) that ends the
moment the event happens. Many stand-ins carry a **ceiling**, a duration after which a
failing test gives up instead of hanging; a ceiling is reached only by a test that is
already failing, so it is not a real wait.

## Result

Six tests really wait, all in printer delivery. The slice service's tests have none.

| Suite | Real waits |
|---|---|
| Printer delivery's fast suite (`make -C delivery test`) | 2 |
| Printer delivery against the simulated printer (`make -C delivery test-sim`) | 2 |
| Printer delivery's together run on real threads (`make -C delivery test-together`) | 2 |
| The slice service's fast suite (`make -C slice test`) | 0 |

Outside every suite, `delivery/daemon/tests/hardware_smoke.py` (run by
`make -C delivery hardware-smoke`, which starts a real print on a real printer) sleeps on
purpose; it is a script for the real printer, not a test of the suites.

Outside the folders searched, the real-Orca suite in `slice/tests_orca/` runs real Orca
against real time limits (for example a 0.5 s limit at `test_orca.py:407`, and a plate
asserted to finish under 60 s at `test_orca.py:671`); that is Orca's own time, which only
real Orca can show, not a wait of the test's.

## The real waits

| File | Line | Test | Why it is real |
|---|---|---|---|
| `delivery/daemon/tests/test_daemon_run_loop.py` | 917 (clock at 929) | `test_stop_ends_a_job_waiting_for_the_printer_promptly_and_never_starts_it` | Fast suite. The run loop gets `time.monotonic` and its default sleep, a wait on its stop event, so its job thread waits a second at a time on the wall clock until the test calls `stop()`. The test itself waits on events, with 10 s ceilings. |
| `delivery/daemon/tests/test_daemon_run_loop.py` | 943 (clock at 961) | `test_stop_ends_the_start_wait_promptly_with_the_printer_unreachable` | Fast suite. The same, in the wait after the start command; ceilings of 10 s and 5 s. |
| `delivery/simulator/tests/test_simulated_printer.py` | 309 | `test_a_reconnect_with_no_new_document_keeps_the_old_age` | Simulated printer. The printer library's MQTT client reconnects after its own one-second delay on the wall clock (comment at 321); the test waits on the reconnect (lines 324-327). |
| `delivery/simulator/tests/test_simulated_printer.py` | 486 | `test_the_simulated_printer_runs_on_its_own_and_plays_a_print` | Simulated printer. The simulator runs on its own thread and plays a status document every 0.05 s of wall-clock time (`step_seconds` at 503, played by `simulator/__main__.py:59-61`); the test waits for the finish, with a 30 s ceiling. |
| `delivery/tests/test_together.py` | 370 | `test_the_together_run_in_process` | Together run (`real_time`). The daemon's clock runs twenty times faster than real time and its sleeps wait on the wall clock (`together/__main__.py:144-153`); the run polls every 0.02 s (`together/__main__.py:166-179`). |
| `delivery/tests/test_together.py` | 377 | `test_the_together_run_over_loopback_on_an_ephemeral_port` | Together run (`real_time`). The same, over loopback. |

## Stand-ins, by file

### Printer delivery

| File | Lines | What it is |
|---|---|---|
| `delivery/conftest.py` | 3-49 | Wraps every sleep a test injects into the daemon in a bound (`SleepBound`), so no test can put an unbounded sleep in. |
| `delivery/daemon/tests/daemon_fakes.py` | 34-67, 70-108 | `SleepBound` and `FakeClock`: a monotonic clock that moves only when a test or an injected sleep moves it. |
| `delivery/daemon/tests/test_daemon_cli.py` | 107, 178, 266, 315-337, 462, 477, 486, 530 | Fake clock's sleep injected into the run loop and the commands. |
| `delivery/daemon/tests/test_daemon_cli.py` | 381 | `join(5)` on a thread: waits on its end; 5 s is a ceiling. |
| `delivery/daemon/tests/test_daemon_config.py` | 176, 185-193, 215, 229-234, 249-254, 266-270 | Injected sleep and clock for the wait for a configuration file. |
| `delivery/daemon/tests/test_daemon_job_flow.py` | 35-45, 112, 260, 325, 345, 368, 377, 394, 431, 454, 601-615, 639, 646, 673, 694, 741, 756, 830-836, 919 | Fake clock's sleep with a hook run at each sleep, which puts the printer's next state in order. |
| `delivery/daemon/tests/test_daemon_run_loop.py` | 48, 282-315, 575-581, 727-735, 778-784, 870-876, 894-899, 1005-1009, 1022-1033, 1052-1378 | Fake clock's sleep, and `at_sleep`, which runs a step after the n-th sleep. |
| `delivery/daemon/tests/test_daemon_start_record.py` | 144-149, 170, 181, 217, 240, 253, 306, 328, 376-381, 415-419 | Fake clock's sleep with a step at each. |
| `delivery/daemon/tests/test_daemon_portability.py` | 90 | A subprocess with `timeout=60`: waits on its exit; 60 s is a ceiling. |
| `delivery/daemon/tests/test_daemon_portability.py` | 167, 200, 207-213 | Fake clock's sleep for the `record` command. |
| `delivery/daemon/tests/test_daemon_printer.py` | 673-677 | `Event.wait(5)` on another thread's log line; 5 s is a ceiling. |
| `delivery/daemon/tests/test_daemon_printer.py` | 918 | `timeout=5.0` passed to discovery with a fake socket; nothing waits. |
| `delivery/daemon/tests/test_daemon_relay_client.py` | 382 | `timeout=7.5` passed to a fake session and asserted; nothing waits. |
| `delivery/relay/tests/test_relay_deliveries.py` | 237-262 | The relay's own wait, woken by a change on real threads; `Event.wait(10)`, `join(timeout=5)` and `timeout=3600` are ceilings. |
| `delivery/relay/tests/test_relay_deliveries.py` | 269 | `timeout=0`: no waiting. |
| `delivery/relay/tests/test_relay_routes.py` | 326-343 | A barrier lines up eight threads; `timeout=30` on the barrier and the joins are ceilings. |
| `delivery/tests/link_faults.py` | 63, 588-618, 685-694 | The shop of faults: the job thread's sleep and `drive` move simulated time a step at a time. |
| `delivery/tests/test_start_decided.py` | 369-378 | `drive_with_deaths` moves simulated time a second at a time. |
| `delivery/tests/test_together.py` | 54-62, 82, 163, 232 | The bench's `advance`, a fake wall clock and monotonic clock. |
| `delivery/simulator/tests/test_simulated_printer.py` | 64-78, 93, 135, 140, 293, 363, 389 | `wait_until`: waits on the printer library's message callback, with a 5 s ceiling. |
| `delivery/simulator/tests/test_simulated_printer.py` | 96-146, 445-479, 667-681 | Fake clock's sleep injected into the daemon, which lets the simulated printer catch up on each sleep. |
| `delivery/simulator/tests/test_simulated_printer.py` | 132, 137, 324, 520, 639 | `sim.wait_for`: a condition on the simulated printer's own record, with a 10 s ceiling (`simulator/printer.py:209-213`). |

The suite against the simulated printer passes real messages over loopback sockets, so
the order of its network events is the order the sockets deliver them, which the test
waits on rather than sets.

### The slice service

| File | Lines | What it is |
|---|---|---|
| `slice/tests/helpers.py` | 26, 42 | `FAILSAFE_S = 10`, the ceiling on every wait for a process, a thread or an event. |
| `slice/tests/test_jobs.py` | 3, 18, 61-71, 94, 133, 155, 219-521, 609 | Synchronous stand-ins for the executor, an injected clock, and `Event.wait`, `join` and `pool.wait` with the ceiling. |
| `slice/tests/test_orca_runner.py` | 4, 49-63 | `gone()`: a blocking lock in a thread, released when the stand-in Orca exits; never a sleep. |
| `slice/tests/test_orca_runner.py` | 284-288, 393, 453-458, 714-718, 801-806 | `Event.wait` with the ceiling, released by the stand-in's signal or progress. |
| `slice/tests/test_orca_runner.py` | 1192-1205 | A subprocess killed by the test, then `wait()` on its exit. |
| `slice/tests/test_cli.py` | 81 | `Event().wait(FAILSAFE_S)`, ended at once by the signal the test sends. |
| `slice/tests/test_web.py` | 188 | `join(FAILSAFE_S)` on the runner thread. |
| `slice/tests/test_install_orca.py` | 49 | A subprocess with `timeout=60`: waits on its exit; a ceiling. |
| `slice/tests/fake_orca.py` | 81, 113, 141, 214 | The stand-in Orca waits for a signal (`signal.pause()`), so a test can wait for its death without sleeping. |
