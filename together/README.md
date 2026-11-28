# The joined suite

The suite that runs the real front server and the real slice service together on one
machine, outside the components' fast suites. What it is for and what it must cover are in
the front server's details file,
[The joined suite](../front/README-details.md#running-phase-2-on-one-machine), and in the
architecture's [Keeping it true](../docs/architecture.md#keeping-it-true).

```
make -C together install     # once: this suite's environment and the two components'
make -C together test        # the joined suite, with the slice service's stand-in Orca
make -C together test-orca   # one walk with the real Orca, under the real-Orca lock
```

## How it runs

Each test starts a slice service and a front server of its own from their start commands,
each on a port the system chooses and with fresh folders under the test's own temporary
folder, and stops them at its end. It reaches the two only through their start commands,
their HTTP interfaces and the folders it gave them, never by importing their code.

- **The slice service** runs with the slice service's stand-in for Orca
  (`slice/tests/fake_orca.py`), through a small wrapper the suite writes and names in
  `PENGUIN_SLICE_ORCA`. The wrapper reads the stand-in's mode from a file at each slice, so
  a test says how the next slice goes (sliced, refused by Orca, held until the test lets it
  go) without starting the slice service again. The stand-in ends itself 25 seconds after
  it starts whatever it was asked to do, so a slice held for the test is let go by then at
  the latest: that slice then fails as an Orca that died, and the test sees a failed slice,
  not a held one. No test holds a slice longer than about 16 seconds. A restart starts a
  new slice service process on the same port; should another process take that port in
  the moment between the two, the new slice service exits saying it cannot listen there,
  and the test fails at once with that line.
- **The front server** runs with the development identity, a cookie key the suite makes (so
  a restart signs nobody out), a state folder, a log folder and a folder of page files.
  Until the browser tests arrive the page files are a one-line page the suite writes; the
  front server needs one to start.
- **The page** (`joined/page.py`) drives the front server's routes over HTTP as the wizard
  does: the trip that signs in, the current group, the page's version and the wizard's mark
  on each request, and the progress stream read as the browser reads it.

Every wait is on an event: a line a server writes when it listens or when something
happens, a report on a progress stream, a process ending. Behind each is a backstop
(`joined/waits.py`) that fails the test, naming what it waited for. Each server's output is
kept in `slice.log` and `front.log` in the test's temporary folder, which pytest prints
when a test fails.

## Where the tests are

| Folder | What |
|---|---|
| `joined/` | The fixtures: the two servers, the page, the plates |
| `tests/` | The joined suite, `make -C together test` |
| `tests_orca/` | The one walk with the real Orca, `make -C together test-orca` |

The browser tests (phase 2's last batch) go beside these in `tests/`, taking the same
`slice_service` and `front_server` fixtures and driving them through Chromium in place of
`page`.
