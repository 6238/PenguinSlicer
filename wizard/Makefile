.PHONY: install check-node sync install-browser test test-page test-tools test-browser build look look-parts look-parts-step \
	look-layout-step measure-layout \
	trials trials-preview trials-geometry trials-parts trials-serve

UV ?= uv
NODE ?= node
# The project's own Python, called directly so that a time limit put on `make` or on this
# command bounds the test process itself, not a `uv run` wrapper.
PY = $(CURDIR)/.venv/bin/python
# A bound on each test, so that a test that hangs fails instead of holding the suite.
NODE_TEST_TIMEOUT_MS ?= 60000
# Playwright's browsers go where PLAYWRIGHT_BROWSERS_PATH says, unless that folder cannot be
# written (a machine whose /opt/ms-playwright is read-only and holds another revision); then
# into Playwright's own default, ~/.cache/ms-playwright, shared by every checkout.
BROWSERS := $(shell d="$${PLAYWRIGHT_BROWSERS_PATH:-$$HOME/.cache/ms-playwright}"; \
	if [ -w "$$d" ] || { [ ! -e "$$d" ] && mkdir -p "$$d" 2>/dev/null; }; then echo "$$d"; \
	else echo "$$HOME/.cache/ms-playwright"; fi)
export PLAYWRIGHT_BROWSERS_PATH := $(BROWSERS)
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
# random order (Node prints the seed), then the tools' tests (pytest-randomly prints its seed
# in pytest's header, "Using --randomly-seed=<seed>", so pytest runs without -q, which hides it).
test: check-node test-page test-tools

test-page:
	$(NODE) --test --test-randomize --test-timeout=$(NODE_TEST_TIMEOUT_MS) '$(CURDIR)/tests/**/*.test.js'

test-tools:
	$(PY) -m pytest $(CURDIR)/tests/python

# The tests in Chromium, after the build.
test-browser: build
	$(PY) -m pytest $(CURDIR)/tests_browser

# wizard/dist/ from wizard/src/ and wizard/vendor/.
build:
	$(PY) $(CURDIR)/build.py

# Pictures of the panel as a whole beside the mockup's, at 320, 480, 520 and 680 px, into
# docs/orchestration/phase-2/look/wizard-2/, for a person to look at.
look: build
	$(PY) $(CURDIR)/tests_browser/look.py

# The picture of each kept part as its row will show it, at 88 pixels, drawn by the page's own
# worker in Chromium, into docs/orchestration/phase-2/look/wizard-3/, with the main thread's
# longest hold for each part.
look-parts: build
	$(PY) $(CURDIR)/tests_browser/look_parts.py

# Pictures of the Parts step beside the mockup's, in each state the mockup shows and in the
# screens it never drew, at 320, 480, 520 and 680 px, into docs/orchestration/phase-2/look/wizard-4/.
look-parts-step: build
	$(PY) $(CURDIR)/tests_browser/look_parts_step.py

# Pictures of the Layout step beside the mockup's, in each state the mockup shows, at 320, 480, 520
# and 680 px, into docs/orchestration/phase-2/look/wizard-5b/.
look-layout-step: build
	$(PY) $(CURDIR)/tests_browser/look_layout_step.py

# The Layout view's frame rate while dragging and turning at 150 instances, on this machine, into
# docs/orchestration/phase-2/look/wizard-5b/frame-rate.json.
measure-layout: build
	$(PY) $(CURDIR)/tests_browser/measure_layout.py

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
