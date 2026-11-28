.PHONY: install test test-orca

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
# The limit on the address space is inherited by the servers a test starts, which is what
# bounds them too; the real Orca run leaves it off, since the slice service sets Orca's own.
BOUNDED = $(TIMED) prlimit --as=$$(numfmt --from=iec $(RUN_MEMORY)) --
PYTEST_ARGS = -m pytest -c $(CURDIR)/pyproject.toml --rootdir=$(CURDIR)
PYTEST = $(BOUNDED) $(PYTHON) $(PYTEST_ARGS)

# The suite's environment, and the two components' environments it starts them from. The
# real Orca (about 506 MB) is installed only by test-orca.
install:
	$(UV) sync --project $(CURDIR)
	$(MAKE) -C $(CURDIR)/../slice sync
	$(MAKE) -C $(CURDIR)/../front install

# The joined suite: the real slice service with the slice service's stand-in Orca and the
# real front server with the development identity, on ports the system chooses, with fresh
# folders for each test. One test at a time, in random order (pytest-randomly prints the
# seed; rerun one order with `--randomly-seed=<seed>`).
test:
	$(PYTEST) $(CURDIR)/tests

# One walk from upload to download with the real Orca, under the real-Orca lock. Not part of
# `test`; it installs the pinned Orca first.
test-orca:
	$(MAKE) -C $(CURDIR)/../slice install-orca
	mkdir -p $(dir $(ORCA_LOCK))
	flock $(ORCA_LOCK) $(TIMED) $(PYTHON) $(PYTEST_ARGS) -v -p no:randomly $(CURDIR)/tests_orca
