"""The wizard in Chromium: the page the front server serves from the wizard's build, driven
through Playwright for Python, headless, with no graphics card (Chromium draws 3D in software).

The page runs on its own real clock, as it does for a user: the two servers are real processes,
which take no fake clock. Every wait is for an event, the page reaching a state it is asked
about on each animation frame (Playwright's `wait_for_function`), behind the suite's backstop,
which fails the test naming what it waited for. The running wizard is reached as the page's own
entry module exports it (`(await import(<main.js>)).wizard`), as the wizard's own browser tests
reach it; a test acts through what a user sees (the buttons, the file chooser, the layer bar)
and reads the wizard's state only to know when a step has settled.
"""

import re

from playwright.sync_api import Error as PlaywrightError

from .paths import ROOT
from .waits import BACKSTOP_S

WIZARD_DIST = ROOT / "wizard" / "dist"
BACKSTOP_MS = BACKSTOP_S * 1000


def main_module(dist=WIZARD_DIST):
    """The built address of the page's entry module, as `index.html` names it."""
    html = (dist / "index.html").read_text(encoding="utf-8")
    return re.search(r'src="(/assets/main\.[0-9a-f]{12}\.js)"', html).group(1)


class Wizard:
    """One tab of the wizard, opened at the front server's address."""

    def __init__(self, context, front, *, width=480, height=900, dist=WIZARD_DIST):
        self.context = context
        self.front = front
        self.main = main_module(dist)
        self.page = context.new_page()
        self.page.set_default_timeout(BACKSTOP_MS)
        self.page.set_viewport_size({"width": width, "height": height})
        #: What the page's own code threw or wrote as an error: a test ends asserting none.
        self.problems = []
        # Chromium itself writes an error for every answer of status 400 or more ("Failed to load
        # resource"); those are answers the page reads (a refusal, a restart), not its faults.
        self.page.on("console", lambda m: self.problems.append(m.text) if m.type == "error"
                     and not m.text.startswith("Failed to load resource:") else None)
        self.page.on("pageerror", lambda e: self.problems.append(str(e)))
        #: Every answer the page received from the front server, (method, path, status).
        self.answers = []
        self.page.on("response", lambda r: self.answers.append(
            (r.request.method, r.url.removeprefix(front.url), r.status)))

    # Opening.

    def open(self):
        """Go to the front server's address as a user does: `/` sends a browser with no
        sign-in on the trip, which signs in the development identity and comes back."""
        self.page.goto(self.front.url + "/")
        self.wait_opened()
        return self

    def wait_opened(self):
        self.page.wait_for_selector('html[data-started="true"]', state="attached")
        self.page.wait_for_selector('html[data-opened="true"]', state="attached")
        self._bind()

    def reload(self):
        """A refresh of the tab: its storage kept, the page loaded again."""
        self.page.reload()
        self.wait_opened()

    def _bind(self):
        """The running wizard, kept on the page for the waits below (each load anew)."""
        self.page.evaluate("async (url) => { window.__joinedWizard = (await import(url)).wizard; }", self.main)

    # Asking the page.

    def run(self, body, arg=None):
        """`body`, the text of an async function of (wizard, arg), run against the wizard."""
        return self.page.evaluate(
            f"async ([url, arg]) => {{ const {{ wizard }} = await import(url); "
            f"return (async (wizard, arg) => {{ {body} }})(wizard, arg); }}", [self.main, arg])

    def until(self, condition, arg=None, what=None, backstop_ms=BACKSTOP_MS):
        """Wait until `condition`, the body of a function of (wizard, arg), is true, asked on
        each animation frame; fails at the backstop naming what was awaited and the state."""
        try:
            self.page.wait_for_function(
                f"([arg]) => {{ const wizard = window.__joinedWizard; if (!wizard) return false; "
                f"return Boolean((() => {{ {condition} }})()); }}", arg=[arg], timeout=backstop_ms)
        except PlaywrightError as exc:
            state = self.state()
            raise AssertionError(f"the page never reached {what or condition}: {exc.message.splitlines()[0]}"
                                 f"\nits state: {state}\nits problems: {self.problems}") from None

    def state(self):
        """What a failure message shows of the page: its step, the slicing's model, its text."""
        try:
            return self.run("const m = wizard.slicing.model(); return {step: wizard.store.get().step, "
                            "slicing: {kind: m.kind, stage: m.card?.stage ?? null, report: m.report ?? null}, "
                            "messages: [...document.querySelectorAll('.msg, .notice')].filter((e) => e.offsetParent)"
                            ".map((e) => e.innerText)};")
        except PlaywrightError as exc:
            return f"(not readable: {exc.message.splitlines()[0]})"

    def step(self):
        return self.run("return wizard.store.get().step;")

    def kind(self):
        """What the Preview step shows: idle, card, busy, failed, done or expired."""
        return self.run("return wizard.slicing.model().kind;")

    # Doing what a user does.

    def add_parts(self, paths, units="mm"):
        """Choose `units` beside the upload area and the files in its chooser, then wait until
        each row has arrived, been uploaded and drawn."""
        self.page.check(f"#upload-units input[value={units}]")
        self.page.set_input_files("#f-upload", [str(p) for p in paths])
        self.until(f"return wizard.parts.rows().length === {len(paths)} "
                   "&& wizard.parts.rows().every((r) => !r.arriving && r.drawn);",
                   what=f"{len(paths)} parts uploaded and drawn")

    def next(self, step):
        """Press Next and wait for `step`."""
        self.page.click("#btn-next")
        self.until(f"return wizard.store.get().step === {step!r};", what=f"the step {step}")

    def go(self, step):
        """Press the step's tab and wait for it."""
        self.page.click(f"#stepbar li[data-step={step}]")
        self.until(f"return wizard.store.get().step === {step!r};", what=f"the step {step}")

    def layout_settled(self, instances):
        """The Layout step with `instances` placed, every one inside the plate and clear of the
        others, and nothing left in hand."""
        self.until(f"return wizard.layout.model().instances.length === {instances} "
                   "&& wizard.layout.model().instances.every((i) => i.bounds) "
                   "&& wizard.layout.model().status.ok;", what=f"{instances} instances laid out")
        self.run("await wizard.layout.idle();")

    def to_preview(self, paths, instances=None):
        """Add `paths`, go through Settings and Layout, and enter the Preview step, which
        submits the plate."""
        self.add_parts(paths)
        self.next("settings")
        self.next("layout")
        self.layout_settled(len(paths) if instances is None else instances)
        self.next("preview")

    def card_stage(self, words):
        """Wait until the slicing card's stage line says `words`."""
        self.until("const m = wizard.slicing.model(); return m.kind === 'card' && m.card.stage === arg;",
                   arg=words, what=f"the slicing card saying {words!r}")

    def stage_line(self):
        return self.page.locator("#slice-stage").inner_text()

    def sliced(self, other_than=None):
        """Wait until the Preview step shows the result; gives the sliced file's details.
        After an action that slices again, `other_than` names the slice job the page showed
        before it, whose result or failure may still be on the page for a moment: then only
        the result of another slice job ends the wait."""
        if other_than is None:
            self.until("const m = wizard.slicing.model(); return (m.kind === 'done' && m.details) "
                       "|| ['failed', 'busy', 'expired'].includes(m.kind);", what="the slice's end")
        else:
            self.until("const m = wizard.slicing.model(); "
                       "return m.kind === 'done' && Boolean(m.details) && m.details.slice !== arg;",
                       arg=other_than, what=f"the result of a slice job other than {other_than}")
        assert self.kind() == "done", self.state()
        return self.run("return wizard.slicing.model().details;")

    def layer_preview_drawn(self):
        """Wait until the layer preview has drawn its first layer (the layer bar's buttons are
        on once it has); gives the readout."""
        try:
            self.page.wait_for_function("() => !document.getElementById('btn-layer-up').disabled")
        except PlaywrightError as exc:
            raise AssertionError(f"the layer preview never drew: {exc.message.splitlines()[0]}"
                                 f"\nits readout: {self.readout()!r}\nthe page: {self.state()}"
                                 f"\nits problems: {self.problems}") from None
        return self.readout()

    def readout(self):
        return self.page.locator("#layer-readout").inner_text()

    def download(self):
        """Press Download the sliced file on the Send step; gives (the download, its bytes)."""
        with self.page.expect_download() as caught:
            self.page.click("#btn-do")
        download = caught.value
        with open(download.path(), "rb") as saved:
            return download, saved.read()

    def close(self):
        self.page.close()
