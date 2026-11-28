# Batch together-2-browser-and-wizard-seam: the record

The batch joins the wizard and the front server for the first time: a review of the seam
between them, written up in [the record of the seam](../seam-wizard-front.md); the browser
half of the joined suite in `together/` ([its README](../../../../together/README.md)), the
real wizard driven in Chromium over the real front server and the real slice service; one
browser walk with the real Orca; the fixes the joining called for; and a run by hand of
[Running phase 2 on one machine](../../../../front/README-details.md#running-phase-2-on-one-machine)
from a clean checkout. It builds the rest of item 20 of the front server's phase 2 list
([By phase](../../../../front/README-details.md#phase-2-one-machine-no-onshape-no-printer)).
Written Sat 2026-11-28, Pacific time.

## Decisions made

1. **The browser tests live in `together/tests/` beside the HTTP tests, named
   `test_browser_*.py`, and share the fixture `slice_service`.** The details file said so.
   The front server for them is a second fixture, `wizard_front`, serving `wizard/dist/`,
   since the HTTP tests' front server serves a one-line page. To overrule: `tests/conftest.py`.
2. **The page runs on its own real clock, and the tests wait for the page to reach a state,
   asked on each animation frame (Playwright's `wait_for_function`), behind the suite's
   60-second backstop.** The quality bar wants a fake clock a test moves; the two servers are
   real processes that take no fake clock, and the page's progress, retries and stream
   timers must run against them. Each wait is for an event (the page's state), never a
   duration. The wizard's own browser tests do the same on their real-clock tests. To
   overrule: install Playwright's fake clock in `Wizard` and move it in each wait, which the
   servers' real timers would then outrun.
3. **The address-space limit moves from pytest to each server.** Chromium cannot start under
   the 4 GB limit the first half put on pytest (it died on `SIGTRAP` at launch, and left a
   core file). Chosen: the suite runs each server through `prlimit --as` with the figure the
   Makefile gives in `JOINED_SERVER_AS_BYTES`; pytest and Chromium keep the time limit only.
   The real-Orca run gives none, as before. To overrule: `SERVER_AS_BYTES` in
   `joined/processes.py` and `SERVER_LIMIT` in `together/Makefile`.
4. **The bytes downloaded are compared with a copy the stand-in's wrapper keeps.** "The
   downloaded bytes being the ones the slice service made": the slice service deletes its copy
   once the front server has stored it, so the suite cannot ask for it afterwards. Chosen: a
   test marked `keep_sliced` gets a wrapper that runs the stand-in as its child and then copies
   each `.gcode.3mf` it wrote; the slice service ends Orca by its process group, which holds
   both. Only marked tests change the wrapper, so the first half runs as before. To overrule:
   `write_fake_orca(kept=…)` in `joined/servers.py`.
5. **A user's drag on the Layout view is made through the layout's own move**
   (`wizard.layout.place` and `endDrag`), as the wizard's browser tests make it, in the
   scenario of a changed plate. The 3D view's drag is the wizard suite's to test; the seam is
   what the changed plate does across the servers. The move tries four directions and takes
   the first that leaves the plate fitting, so the test does not depend on where Arrange put
   the parts. To overrule: `move_first_instance` in `tests/test_browser_scenarios.py`.
6. **The scenarios chosen** (asked for: two or three of common use, from what the review finds
   least covered): the owner's three (a slice that fails, with its action; a plate changed
   while slicing and after; a page reloaded while its slice runs, following the same slice job
   to its result with no second submission), and a fourth, settings changed in advanced mode
   with every setting of the real table tried at its bounds. Reason for the fourth: the review
   found the two checks of a setting's value, the wizard's and the slice service's, written
   separately and never compared, the wizard's tests reading a hand-written table of nine
   settings. The reload scenario was first left out, as crossed by the restart rows, and added
   by the builder who finished the batch: those rows show a page coming back only to a slice
   job the slice service lost, never to one still running. It passed when first run, the
   seam holding there. The reasons are in
   [the record of the seam](../seam-wizard-front.md#which-scenarios-the-joined-suite-adds). To
   overrule: drop a test from `tests/test_browser_scenarios.py` or `test_browser_settings.py`.
7. **The bounds check asks the slice service directly, with a plate naming a part it does not
   hold.** The slice service checks the overrides before the parts, so a value it accepts is
   answered `slice.part_missing` and one it refuses `slice.bad_overrides`, and no slice job
   starts either way; the 1,299 values take 17 seconds. Through the front server, the
   accepted ones would each start a slice job and its limit of 30 submissions a minute would
   stop the test. The front server passes the overrides unchanged, which the first half
   shows. To overrule: `test_every_setting_at_its_bounds_…` in
   `tests/test_browser_settings.py`.
8. **Mismatch 1 (the sign-in trip) is fixed in the wizard, in its phase 2 form.** The contract
   and the front server's details say the page makes the trip on `front.not_signed_in`; the
   wizard's details put it in phase 3. Chosen: the trip as the wizard's details describe it
   for phase 3, through the development identity's `/signin`, noted in the tab (the record
   `signInTrip`, kept as `penguinslicer.sign_in_trip` in `sessionStorage`), made at a quiet
   moment (no pointer down, no field being typed in), made once; a trip that failed shows the
   refusal where the request was made, not yet the phase 3 message in place of the step. The
   quiet moment does not yet count an open menu or confirmation. Reason: the guides support
   it (the wizard's guide's "Signing in", the front server's "The cookie key on one machine",
   the architecture's front server table) and the other fix, a cookie key that outlives a
   restart on one machine, would need a secret kept on disk or typed by the owner. To
   overrule: `src/signing-in.js` and the `signIn` hook in `src/api.js`.
9. **The wizard's browser fake now keeps a sign-in, off unless a test asks.**
   `new_cookie_key()` turns it on and makes every earlier cookie unreadable; `/signin` sets
   the cookie. Off by default so that no other test of the wizard's changes. To overrule:
   `fake_front_server.py`.
10. **Mismatch 2 (the stand-in's G-code) is fixed in the stand-in,** in the slice service's
    test folder, which the joined suite runs: the same header and moves, in 42 layers marked
    as the pinned Orca marks them. Reason: the stand-in departed from "what Orca exports";
    the wizard reads the real format. To overrule: `layered_gcode` in
    `slice/tests/fake_orca.py`.
11. **Mismatches 3 and 4 are recorded and left.** Neither breaks a written rule nor anything a
    user does; each fix would move a fake's default answer under many tests or change a report
    another builder's tests pin. Mismatch 4's two readings are in the record of the seam.
12. **The real-Orca browser walk slices the pulley,** a compact real part the wizard lays out as
    it comes, and changes the sparse infill density to 35 % in advanced mode, so that the walk
    also shows a setting the page wrote is the one the real Orca sliced with (read from
    `Metadata/project_settings.config`). It slices in under a second. It starts its own front
    server and browser inside the test, since the target holds the lock for the whole run. To
    overrule: `tests_orca/test_real_orca_browser.py`.
13. **Playwright is pinned in `together/` to the wizard's version (1.65.2),** so that both
    drive the one Chromium that `make -C wizard install-browser` installs, and `together`'s
    `install` runs the wizard's `sync install-browser` (not its `install`, which also asks for
    Node, which the suite does not use). The Makefile finds the browsers as the wizard's does.
14. **Chromium's own console line for an answer of status 400 or more is not counted as a
    fault of the page** (`Wizard.problems`). Those answers are refusals and restarts the
    tests cause on purpose. Every other console error and every uncaught error is.
15. **The by-hand run used the documented ports 8640 and 8600,** which were free, and started
    the slice service under the real-Orca lock (`flock /var/tmp/penguin-locks/real-orca.lock
    uv run --project slice …`), a rule of this shared machine, not of the document. Its
    commands worked as written; the document needed no correction. The folders it made under
    `/var/tmp` were removed afterwards.

## Mismatches between the two sides

Each in full, with its evidence, in [the record of the seam](../seam-wizard-front.md#mismatches).

1. **An open page answered "not signed in" showed the refusal instead of making the trip.**
   The wizard departed from the contract and from the front server's details, which say a
   front server restarted on one machine with no cookie key signs the page in again by the
   trip. The page showed "You are not signed in to PenguinSlicer in this browser." with Slice
   again and Back to Layout. Fixed in the wizard (decision 8); its browser fake, which answered
   whatever cookie came, now keeps a sign-in (decision 9).
2. **The stand-in Orca's sliced file had no layers the layer preview could draw.** The
   stand-in departed from the sliced file's contract; the wizard's fakes serve a real Orca file,
   which hid it. Fixed in the stand-in (decision 10).
3. **The hand-written `done` report carries a stage, its label and a fraction; the real one
   carries none.** The examples depart from the real reports; no reader acts on them. Left,
   and the examples' README says so.
4. **The slice service's first running report has no stage,** so the slicing card's stage line
   is blank for a moment. The contract is silent. Left, with the two readings in the record of
   the seam.

## Targets missed

1. **The phase 3 form of a failed sign-in trip is not built:** the refusal is shown where the
   request was made, not as the message with Sign in in place of the step; and the quiet
   moment the trip waits for does not count an open menu, joined box or confirmation, which
   the wizard's guide lists.
2. **The quality bar's fake clock is not used in the browser half** (decision 2): the page
   runs on the real clock, its waits being for events behind a 60-second backstop.

## Not done

1. **The front server's restart rows that need a page**, other than the sign-in across a
   restart with a new key: the task asked for the slice container's rows, and the wizard's own
   suite shows a page reloading for a newer version against its fake.
2. **A drawing summary across the seam:** the page sends one only for a use of a view whose
   frames were measured, which the joined walk does not make; a failure report is checked
   instead.
3. **Expiry at two hours, a fifth progress stream, and the limits on how fast** are still
   shown only against fakes; each would need a duration or a setting neither server has.
4. **Mismatches 3 and 4 are not fixed** (decision 11).

## For the owner to look at

- **The wizard on one machine, by hand.** From the repository's root, in three terminals,
  as [Running phase 2 on one machine](../../../../front/README-details.md#running-phase-2-on-one-machine)
  says:

  ```
  make -C slice install && make -C wizard install && make -C front install    # once
  uv run --project slice python -m penguin_slice serve --work /var/tmp/penguin-slice
  make -C wizard build
  PENGUIN_DEV_IDENTITY=1 uv run --project front python -m penguin_front serve
  ```

  then open `http://127.0.0.1:8600/` in Chrome, add STL files from
  `contracts/examples/parts/real/` with "mm" chosen, and press Next through to Download.
  Ctrl-C stops each server. A walk this way on an aarch64 Linux machine sliced the pulley and
  the inner spacer with the real Orca in 0.7 seconds; its pictures, at 520 px:
  [parts](../look/together-2/1-parts.png), [settings](../look/together-2/2-settings.png),
  [layout](../look/together-2/3-layout.png), [slicing](../look/together-2/4-slicing.png),
  [preview](../look/together-2/5-preview.png), [send](../look/together-2/6-send.png).
- **The joined suite:** `make -C together install`, then `make -C together test` (both
  halves, with the stand-in Orca), and `make -C together test-orca` (the two walks with the
  real Orca, under the real-Orca lock).
- [The record of the seam](../seam-wizard-front.md), above all its two readings of
  [mismatch 4](../seam-wizard-front.md#4-the-slice-services-first-running-report-has-no-stage).
