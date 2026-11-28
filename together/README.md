# The joined suite

The suite that runs the real front server and the real slice service together on one
machine, and drives the real wizard over them in a browser, outside the components' fast
suites. What it is for and what it must cover are in the front server's details file,
[The joined suite](../front/README-details.md#running-phase-2-on-one-machine), and in the
architecture's [Keeping it true](../docs/architecture.md#keeping-it-true).

```
make -C together install     # once: this suite's environment, the two servers', the wizard's tools and Chromium
make -C together test        # the joined suite, with the slice service's stand-in Orca (builds the wizard first)
make -C together test-orca   # the two walks with the real Orca, under the real-Orca lock
```

## How it runs

Each test starts a slice service and a front server of its own from their start commands,
each on a port the system chooses and with fresh folders under the test's own temporary
folder, and stops them at its end. It reaches the two only through their start commands,
their HTTP interfaces, the folders it gave them and the wizard's built page, never by
importing their code.

- **The slice service** runs with the slice service's stand-in for Orca
  (`slice/tests/fake_orca.py`), through a small wrapper the suite writes and names in
  `PENGUIN_SLICE_ORCA`. The wrapper reads the stand-in's mode from a file at each slice, so
  a test says how the next slice goes (sliced, refused by Orca, held until the test lets it
  go) without starting the slice service again; a test marked `keep_sliced` also has the
  wrapper keep a copy of each sliced file the stand-in writes, to compare with a download.
  The stand-in ends itself 25 seconds after it starts whatever it was asked to do, so a slice
  held for the test is let go by then at the latest: that slice then fails as an Orca that
  died, and the test sees a failed slice, not a held one. No test holds a slice longer than
  about 16 seconds. A restart starts a new slice service process on the same port; should
  another process take that port in the moment between the two, the new slice service exits
  saying it cannot listen there, and the test fails at once with that line.
- **The front server** runs with the development identity, a cookie key the suite makes (so
  a restart signs nobody out, unless a test changes the key), a state folder, a log folder and
  a folder of page files: a one-line page for the HTTP tests, the wizard's build
  (`wizard/dist/`) for the browser tests.
- **The page** (`joined/page.py`) drives the front server's routes over HTTP as the wizard
  does: the trip that signs in, the current group, the page's version and the wizard's mark
  on each request, and the progress stream read as the browser reads it.
- **The wizard** (`joined/browser.py`) is the real one, in Chromium through Playwright for
  Python, headless, drawing in software. A test acts as a user does (the file chooser, the
  buttons, advanced mode's fields, the layer bar, Download) and reads the wizard's state only
  to know when a step has settled. The page runs on its own clock, since the servers are real
  processes with no fake clock.

Every wait is on an event: a line a server writes when it listens or when something
happens, a report on a progress stream, a process ending, the page reaching a state it is
asked about on each animation frame. Behind each is a backstop (`joined/waits.py`, 60 s) that
fails the test, naming what it waited for. Each server's output is kept in `slice.log` and
`front.log` in the test's temporary folder, which pytest prints when a test fails.

**Bounds.** The run has a time limit on pytest's own process, and each server an
address-space limit of 4 GB that the suite gives it (`JOINED_SERVER_AS_BYTES`); pytest itself
has none, since Chromium cannot start under one. The real-Orca run gives none, since the
slice service sets Orca's own.

## Where the tests are

| Folder | What |
|---|---|
| `joined/` | The fixtures: the two servers, the page, the wizard in the browser, the plates |
| `tests/` | The joined suite, `make -C together test`: the HTTP tests, and the browser tests (`test_browser_*.py`) |
| `tests_orca/` | The two walks with the real Orca, `make -C together test-orca` |
