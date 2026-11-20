# Printer delivery: the relay and the daemon. Run from anywhere with `make -C delivery <target>`.
#
#   make test            the fast suite: no socket, no real waiting, random order
#   make test-parallel   the fast suite on two workers (the machine's cap for parallel tests)
#   make test-repeat     the fast suite ten times in a row, each in a new random order
#   make slowest         the fast suite with its ten slowest tests listed
#   make coverage        branch coverage per module under the fast suite
#   make test-together   the together run on real threads (in-process and over loopback)
#   make together        the together run, printing every state change
#   make daemon-tarball  the daemon alone, as one archive, in dist/
#   make hardware-smoke  starts a REAL print on a REAL printer; see daemon/tests/hardware_smoke.py

.PHONY: install test test-parallel test-repeat slowest coverage test-together together \
        daemon-tarball hardware-smoke

UV := uv run --project $(CURDIR)
FAST := -m "not real_time"
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

test-together:
	$(UV) pytest -q -m real_time

together:
	$(UV) python -m together $(ARGS)

# The daemon alone, as one archive, for running it on a laptop against a development
# relay: unpack it, `pip install ./penguincam-printer-daemon` into a venv (its pyproject.toml
# carries the pins), then run `penguincam-printer`. Staged through a directory rather than
# tar's --transform, so it works with BSD tar as well as GNU tar.
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
