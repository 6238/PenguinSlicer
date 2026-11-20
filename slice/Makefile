.PHONY: install sync install-orca test test-parallel test-flakes coverage test-orca test-upstream upgrade-orca

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

# Branch coverage of the package under the fast suite; fails under 100%.
coverage:
	$(UV) run --project $(CURDIR) coverage run --rcfile=$(CURDIR)/pyproject.toml -m pytest -q -p no:randomly $(CURDIR)/tests
	$(UV) run --project $(CURDIR) coverage report --rcfile=$(CURDIR)/pyproject.toml --fail-under=100

# The upstream check: the tests that run the real Orca Slicer, one at a time, each pinning
# one behaviour of the pinned Orca the slice service relies on. Install Orca first.
test-upstream:
	$(PYTEST) -v -p no:randomly --durations=0 $(CURDIR)/tests_orca

test-orca: test-upstream

# Move the Orca pin: fetch and verify VERSION, regenerate the profiles, run the upstream check.
upgrade-orca:
	@test -n "$(VERSION)" || { echo "usage: make upgrade-orca VERSION=x.y.z"; exit 2; }
	$(UV) run --project $(CURDIR) python $(CURDIR)/scripts/upgrade_orca.py $(VERSION)
