.PHONY: install sync install-orca test test-parallel test-flakes coverage test-orca

UV ?= uv
PYTEST = $(UV) run --project $(CURDIR) pytest
# Parallel test workers (this machine's rules allow two) and the runs of test-flakes.
WORKERS ?= 2
RUNS ?= 10

# The Python environment and Orca Slicer (slice/tools/orca, pinned in scripts/install-orca.sh).
install: sync install-orca

sync:
	$(UV) sync --project $(CURDIR)

install-orca:
	$(CURDIR)/scripts/install-orca.sh

# The fast suite: no Orca, no network, no waiting. Random order on every run
# (pytest-randomly prints the seed; rerun one order with `--randomly-seed=<seed>`).
test:
	$(PYTEST) $(CURDIR)/tests

# The fast suite on WORKERS worker processes.
test-parallel:
	$(PYTEST) -q -n $(WORKERS) $(CURDIR)/tests

# The fast suite RUNS times on WORKERS workers, each run in a new random order: the seed is
# drawn fresh from /dev/urandom and printed, so a failing order can be rerun with
# `--randomly-seed=<seed>`.
test-flakes:
	@run=1; while [ $$run -le $(RUNS) ]; do \
		seed=$$(od -An -N4 -tu4 /dev/urandom | tr -d ' '); \
		echo "test-flakes: run $$run of $(RUNS), --randomly-seed=$$seed"; \
		$(PYTEST) -q -n $(WORKERS) -p no:cacheprovider --randomly-seed=$$seed $(CURDIR)/tests \
			|| { echo "test-flakes: FAILED with --randomly-seed=$$seed"; exit 1; }; \
		run=$$((run + 1)); \
	done

# Branch coverage of the package under the fast suite.
coverage:
	$(UV) run --project $(CURDIR) coverage run --rcfile=$(CURDIR)/pyproject.toml -m pytest -q -p no:randomly $(CURDIR)/tests
	$(UV) run --project $(CURDIR) coverage report --rcfile=$(CURDIR)/pyproject.toml

# The tests that run the real Orca Slicer. Slow by design; install Orca first.
test-orca:
	$(PYTEST) -v -p no:randomly --durations=0 $(CURDIR)/tests_orca
