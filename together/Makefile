.PHONY: install wizard-build test test-orca

UV ?= uv
# The real-Orca lock every agent and person on this machine shares: one real Orca at a time
# (CLAUDE.md, "One real Orca at a time").
ORCA_LOCK ?= /var/tmp/penguin-locks/real-orca.lock
# Every run of pytest is bounded on pytest's own process, never on a wrapper such as `uv run`,
# which a timeout would kill while leaving pytest running: a wall-clock limit for the whole run
# and a limit on its address space. The two servers each test starts are processes of their
# own, outside this limit; each test stops them, and pytest's own end stops any left.
RUN_LIMIT_S ?= 900
RUN_MEMORY ?= 4G
PYTHON = $(CURDIR)/.venv/bin/python
TIMED = env MALLOC_ARENA_MAX=2 timeout --kill-after=10 $(RUN_LIMIT_S)
# The limit on the address space is given to each server a test starts
# (`JOINED_SERVER_AS_BYTES`, joined/processes.py), not to pytest: Chromium reserves far more
# address space than it uses and cannot start under it. The real Orca run gives none, since the
# slice service sets Orca's own.
SERVER_LIMIT = JOINED_SERVER_AS_BYTES=$$(numfmt --from=iec $(RUN_MEMORY))
PYTEST_ARGS = -m pytest -c $(CURDIR)/pyproject.toml --rootdir=$(CURDIR)
PYTEST = $(TIMED) $(SERVER_LIMIT) $(PYTHON) $(PYTEST_ARGS)
# Playwright's Chromium, where the wizard's install puts it (wizard/Makefile, BROWSERS): the
# folder PLAYWRIGHT_BROWSERS_PATH names when it can be written, else ~/.cache/ms-playwright.
BROWSERS := $(shell d="$${PLAYWRIGHT_BROWSERS_PATH:-$$HOME/.cache/ms-playwright}"; \
	if [ -w "$$d" ] || { [ ! -e "$$d" ] && mkdir -p "$$d" 2>/dev/null; }; then echo "$$d"; \
	else echo "$$HOME/.cache/ms-playwright"; fi)
export PLAYWRIGHT_BROWSERS_PATH := $(BROWSERS)

# The suite's environment, the two servers' environments it starts them from, and the wizard's
# build tools with Playwright's Chromium. The real Orca (about 506 MB) is installed only by
# test-orca.
install:
	$(UV) sync --project $(CURDIR)
	$(MAKE) -C $(CURDIR)/../slice sync
	$(MAKE) -C $(CURDIR)/../front install
	$(MAKE) -C $(CURDIR)/../wizard sync install-browser

# The wizard's page files, wizard/dist/, which the browser tests' front server serves.
wizard-build:
	$(MAKE) -C $(CURDIR)/../wizard build

# The joined suite: the real slice service with the slice service's stand-in Orca and the
# real front server with the development identity, on ports the system chooses, with fresh
# folders for each test; the browser tests drive the wizard's build in Chromium over the same
# two servers. One test at a time, in random order (pytest-randomly prints the seed; rerun one
# order with `--randomly-seed=<seed>`).
test: wizard-build
	$(PYTEST) $(CURDIR)/tests

# The walks with the real Orca, under the real-Orca lock: one over HTTP, one in the browser.
# Not part of `test`; it installs the pinned Orca first.
test-orca: wizard-build
	$(MAKE) -C $(CURDIR)/../slice install-orca
	mkdir -p $(dir $(ORCA_LOCK))
	flock $(ORCA_LOCK) $(TIMED) $(PYTHON) $(PYTEST_ARGS) -v -p no:randomly $(CURDIR)/tests_orca
