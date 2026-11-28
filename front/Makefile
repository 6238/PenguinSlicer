.PHONY: install test test-parallel coverage

UV ?= uv
# Parallel test workers: this machine's rules allow two.
WORKERS ?= 2
# Every run of pytest is bounded on pytest's own process, never on a wrapper such as
# `uv run`, which a timeout would kill while leaving pytest running: a wall-clock limit for
# the whole run and a limit on its address space, so a test looping on a fake clock fails
# instead of growing to gigabytes.
RUN_LIMIT_S ?= 600
RUN_MEMORY ?= 4G
PYTHON = $(CURDIR)/.venv/bin/python
# glibc reserves 64 MB of address space for each thread's own malloc arena, up to eight per
# processor, which the limit on the address space counts: the test of forty progress
# streams holds about seventy threads, and with an arena each the run passes 4G and fails
# to start threads. Two arenas bound it; the memory used is unchanged.
BOUNDED = MALLOC_ARENA_MAX=2 timeout --kill-after=10 $(RUN_LIMIT_S) prlimit --as=$$(numfmt --from=iec $(RUN_MEMORY)) --
PYTEST = $(BOUNDED) $(PYTHON) -m pytest -c $(CURDIR)/pyproject.toml --rootdir=$(CURDIR)

# The front server's Python environment, with its test tools.
install:
	$(UV) sync --project $(CURDIR)

# The fast suite: no real Orca, no network beyond loopback, no waiting, no fixed ports.
# Random order on every run (pytest-randomly prints the seed; rerun one order with
# `--randomly-seed=<seed>`).
test:
	$(PYTEST) $(CURDIR)/tests

# The fast suite on WORKERS worker processes.
test-parallel:
	$(PYTEST) -q -n $(WORKERS) $(CURDIR)/tests

# Branch coverage of the package under the fast suite.
coverage:
	$(BOUNDED) $(PYTHON) -m coverage run --rcfile=$(CURDIR)/pyproject.toml -m pytest -c $(CURDIR)/pyproject.toml --rootdir=$(CURDIR) -q -p no:randomly $(CURDIR)/tests
	$(PYTHON) -m coverage report --rcfile=$(CURDIR)/pyproject.toml --fail-under=100
