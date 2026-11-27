.PHONY: install check-node sync install-browser test test-page test-tools test-browser build \
	trials trials-preview trials-geometry trials-parts trials-serve

UV ?= uv
NODE ?= node
# The project's own Python, called directly so that a time limit put on `make` or on this
# command bounds the test process itself, not a `uv run` wrapper.
PY = $(CURDIR)/.venv/bin/python
# A bound on each test, so that a test that hangs fails instead of holding the suite.
NODE_TEST_TIMEOUT_MS ?= 60000
# trials-serve: the address the owner's Chrome opens (HOST=0.0.0.0 to reach it from outside
# the machine it runs on).
HOST ?= 127.0.0.1
PORT ?= 8610

# The uv environment and Playwright's Chromium; fails naming the version when Node is older than 24.
install: check-node sync install-browser

check-node:
	python3 $(CURDIR)/scripts/check_node.py $(NODE)

sync:
	$(UV) sync --project $(CURDIR)

install-browser:
	$(PY) -m playwright install chromium

# The fast suite, without a browser window: the page's tests on Node's own runner, in a
# random order (Node prints the seed), then the tools' tests (pytest-randomly prints its seed).
test: check-node test-page test-tools

test-page:
	$(NODE) --test --test-randomize --test-timeout=$(NODE_TEST_TIMEOUT_MS) '$(CURDIR)/tests/**/*.test.js'

test-tools:
	$(PY) -m pytest -q $(CURDIR)/tests/python

# The tests in Chromium, after the build.
test-browser: build
	$(PY) -m pytest -q $(CURDIR)/tests_browser

# wizard/dist/ from wizard/src/ (and, from the skeleton on, wizard/vendor/).
build:
	$(PY) $(CURDIR)/build.py

# The two opening trials of phase 2, each its own entry point: both run, even when the
# first fails, and the target fails when either does.
trials:
	@status=0; $(MAKE) trials-preview || status=1; $(MAKE) trials-geometry || status=1; exit $$status

trials-preview:
	$(PY) $(CURDIR)/trials/preview/run.py

trials-geometry:
	$(PY) $(CURDIR)/trials/geometry/run.py

# Writes the trials' made parts (hub-150k.stl, hex-spacer.stl) into wizard/trials/parts/.
trials-parts:
	$(PY) $(CURDIR)/trials/make_parts.py

# Serves wizard/trials/ (with wizard/vendor/ and the real parts beside it) for the owner's timing.
trials-serve:
	$(PY) $(CURDIR)/trials/serve.py --host $(HOST) --port $(PORT)
