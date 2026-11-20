# Printer delivery: the relay and the daemon. Run from anywhere with `make -C delivery <target>`.
#
#   make test            the fast suite: no socket, no real waiting, random order
#   make test-parallel   the fast suite on two workers (the machine's cap for parallel tests)
#   make test-repeat     the fast suite ten times in a row, each in a new random order
#   make slowest         the fast suite with its ten slowest tests listed
#   make coverage        branch coverage per module under the fast suite
#   make test-properties the random sequences (Hypothesis), before a commit and by reviewers
#   make test-sim       the daemon against the simulated printer, over loopback sockets
#   make test-upstream   the upstream check: the installed printer library, and test-sim
#   make upgrade-printer-library VERSION=x.y.z   move the one pin, re-lock, run the check
#   make test-together   the together run on real threads (in-process and over loopback)
#   make together        the together run, printing every state change
#   make daemon-tarball  the daemon alone, as one archive, in dist/
#   make hardware-smoke  starts a REAL print on a REAL printer; see daemon/tests/hardware_smoke.py

.PHONY: install test test-parallel test-repeat slowest coverage test-properties test-sim \
        test-upstream upgrade-printer-library test-together together daemon-tarball \
        hardware-smoke

UV := uv run --project $(CURDIR)
FAST := -m "not real_time and not simulator and not properties"
REPEATS ?= 10

install:
	uv sync --project $(CURDIR)

test:
	$(UV) pytest -q $(FAST)

test-parallel:
	$(UV) pytest -q $(FAST) -n 2

test-repeat:
	@for run in $$(seq 1 $(REPEATS)); do \
		echo "== run $$run of $(REPEATS)"; \
		$(UV) pytest -q $(FAST) -p randomly || exit 1; \
	done

slowest:
	$(UV) pytest -q $(FAST) --durations=10 --durations-min=0

coverage:
	$(UV) coverage erase
	$(UV) coverage run -m pytest -q $(FAST) -p no:randomly
	$(UV) coverage report

# Three tests of 60 to 120 random sequences each, on two workers, in a few seconds. A
# failing sequence is reported as found, never shrunk, so a real bug fails the target
# within the per-test limit (30 s, pyproject.toml) plus one more run of that sequence.
test-properties:
	$(UV) pytest -q -m properties -n 2 -p no:randomly

# One worker: each test starts its own simulated printer on ports the system picks.
test-sim:
	$(UV) pytest -q -m simulator -p no:randomly

test-upstream:
	$(UV) pytest -q -m "upstream or simulator" -p no:randomly

upgrade-printer-library:
	@test -n "$(VERSION)" || { echo "usage: make upgrade-printer-library VERSION=x.y.z"; exit 2; }
	$(UV) python scripts/upgrade_printer_library.py $(VERSION)

test-together:
	$(UV) pytest -q -m real_time

together:
	$(UV) python -m together $(ARGS)

# The daemon alone, as one archive: unpack it, `pip install ./penguincam-printer-daemon`
# into a venv (its pyproject.toml carries the pins), then run it with
# `python -m penguin_delivery_daemon`. Staged through a directory rather than tar's
# --transform, so it works with BSD tar as well as GNU tar.
DAEMON_TARBALL ?= dist/penguincam-printer-daemon.tar.gz
daemon-tarball:
	@rm -rf dist/penguincam-printer-daemon
	@mkdir -p dist/penguincam-printer-daemon
	@cp -R daemon/penguin_delivery_daemon daemon/pyproject.toml dist/penguincam-printer-daemon/
	@find dist/penguincam-printer-daemon -name __pycache__ -type d -prune -exec rm -rf {} +
	@tar -C dist -czf $(DAEMON_TARBALL) penguincam-printer-daemon
	@rm -rf dist/penguincam-printer-daemon
	@echo "wrote $(DAEMON_TARBALL)"

hardware-smoke:
	$(UV) python daemon/tests/hardware_smoke.py
