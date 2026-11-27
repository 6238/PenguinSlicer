# Phase 2, batch wizard-0-project: the wizard's project and the trials' inputs

The builder's record of the first half of item 1 of
[the wizard's details, "By phase"](../../../../wizard/README-details.md#phase-2-one-machine):
the project and its tools, and the inputs of the two trials. The trials themselves are the
next two batches. Written on Fri 2026-11-27 (Pacific time) on branch
`phase-2/wizard-0-project`.

What was built:

- The `uv` project [wizard/pyproject.toml](../../../../wizard/pyproject.toml) and the
  [Makefile](../../../../wizard/Makefile) with `install`, `test`, `test-browser`, `build`,
  `trials` (running `trials-preview` and `trials-geometry`), `trials-parts` and
  `trials-serve`; Node's version check.
- The fast suite: on Node's runner, the search of the page's modules for `setTimeout`,
  `setInterval`, `Date.now` and `fetch` outside `wizard/src/seams/`, and the check of
  `index.html` against the built-files contract; on pytest, the tools' tests.
- The eight real parts copied to `contracts/examples/parts/real/`, hashes verified equal to
  the slice service's, with [a README](../../../../contracts/examples/parts/real/README.md)
  listing them.
- `wizard/trials/make_parts.py` and the committed `hub-150k.stl` and `hex-spacer.stl`.
- three.js 0.170.0 in `wizard/vendor/`, with [its README](../../../../wizard/vendor/README.md).
- The trials' server and the two placeholder entry points
  ([wizard/trials/README.md](../../../../wizard/trials/README.md)).
- A first `build.py`, and the first browser tests with a small fake front server.

## Decisions made

1. **Where the tools' Python tests live.** The details file puts the tests without a
   browser window in `wizard/tests/` and is silent on tests of the Python tools. I put
   them in `wizard/tests/python/`, run by `make test` after the Node tests. The first
   choice, `tests/tools/`, is ignored by the repository's `.gitignore` (which ignores every
   folder named `tools/` for Orca's install), so it was never committed. To overrule: move
   the folder and change the `test-tools` target; a name containing `tools/` needs the
   `.gitignore` narrowed to `slice/tools/`.
2. **The fast suite runs two runners.** The details say the fast suite is Node's test
   runner; the tools (build, the parts' maker, the trials' server) are Python and need
   tests too. `make test` runs `test-page` (Node, random order, 60 s a test) and then
   `test-tools` (pytest, random order, 120 s a test). To overrule: split `test-tools` into
   a target of its own outside `test`.
3. **The seams are the folder `wizard/src/seams/`, and the search also forbids
   `setInterval`.** The details name the three calls and "the seams" without a place. A
   module is a seam when its path under `src/` starts with `seams/`. I added `setInterval`
   because it is a timer and the details say every timer goes through the clock. The
   search skips comments but searches strings (so `self['fetch']` is caught), and matches
   a name reached through the global object. Its known blind spot is a name built from
   pieces (`'set' + 'Timeout'`). To overrule: change `isSeam` and `FORBIDDEN` in
   `wizard/tests/forbidden_calls.js`; the skeleton batch places the clock and the transport
   in `src/seams/` or moves the rule.
4. **three.js 0.170.0, and which of its files.** The details allow a release newer than the
   mockup's 128. I took 170: it is published as ES modules, which the page loads with no
   bundler, and it is the last release whose core is one file. Besides the core I kept the
   example files the trials are most likely to need (orbit controls, buffer utilities,
   convex hull, wide lines), at the package's own paths, so that neither trial's builder
   has to add to `wizard/vendor/` and the two never edit its README at once. The files are
   byte for byte, the npm package's SHA-1 checked against the registry's. To overrule:
   replace the files and the table in one commit, as the vendor README says.
5. **The trials' server serves three folders.** The details say `trials-serve` serves
   `wizard/trials/`; a trial's page also needs three.js and the real parts, which live
   outside it. `wizard/trials/serve.py` serves `wizard/trials/` at `/`, `wizard/vendor/` at
   `/vendor/` and `contracts/examples/parts/real/` at `/parts/real/`, refuses any path with
   `..` and directory listings, says not to cache, and answers only GET and HEAD. A
   trial's script calls its `make_server("127.0.0.1", 0)`. To overrule: change `ROOTS` in
   `serve.py`.
6. **`trials-serve` binds `127.0.0.1:8610` as the details say, with `HOST` and `PORT` to
   change it.** On the Mac the owner reaches it at that address when it runs there; to
   reach it in the agents' container from the Mac it needs `HOST=0.0.0.0`. To overrule:
   change the default `HOST` in the Makefile.
7. **The placeholder entry points fail.** Each says it is a placeholder and exits 1, so
   `make trials` cannot be mistaken for a passing trial. `make trials` runs both even when
   the first fails, and fails when either does. To overrule: make the placeholders exit 0.
8. **A `trials-parts` target, not in the details' table.** It writes the made parts again;
   the fast suite fails, naming that command, when a committed part differs. To overrule:
   remove the target and run the script directly.
9. **The hub's facets: 300 around by 250 along, coordinates rounded to 1e-6 mm.** The
   details fix the shape and the count, not the split. 300 by 250 gives exactly 150,000
   triangles in near-square facets of about 0.27 by 0.25 mm, as the slice service's
   measuring hub was. Rounding each coordinate before storing keeps the bytes from
   depending on the last bit of a machine's sine and cosine. The spacer fans each rim
   segment to the nearer hexagon corner (my own triangulation, 216 triangles as required).
   To overrule: change the constants in `make_parts.py` and run `make -C wizard trials-parts`.
10. **The build is minimal.** The task allows it. `build.py` writes `dist/index.html` and
    hashes every other file of `src/` flat into `dist/assets/`, rewriting the references in
    `index.html`, and refuses what the contract forbids with a sentence. It does not yet
    rewrite names inside assets or build in `wizard/vendor/` (see "Not done").
11. **Playwright's browsers in `~/.cache/ms-playwright` when `PLAYWRIGHT_BROWSERS_PATH`
    cannot be written.** On this machine it points at a read-only `/opt/ms-playwright`
    holding revision 1232, while the Playwright for Python that `uv` resolves (1.65.2)
    needs 1255. The Makefile falls back to Playwright's own default folder, shared by every
    checkout. I did not pin an older Playwright to match the machine's browser, because
    that would tie the project to one container's image. To overrule: pin `playwright` in
    `pyproject.toml` to the version whose Chromium the machine has.
12. **A README beside the real parts.** The details say only to copy the parts. I added
    [contracts/examples/parts/real/README.md](../../../../contracts/examples/parts/real/README.md)
    with each file's hash and the MIT licence the slice service's copy carries, and a
    test of the hashes. To overrule: delete it and the test `test_real_parts.py`.
13. **Which documents I changed.** I updated the wizard's guide and details file and the
    wizard's row of the root `CLAUDE.md` table. I left the plan's "Where things stand"
    ("have no code") and the root `README.md`'s "(not started)" unchanged: other builders
    are editing those files now, and the change is small enough to make when phase 2's
    guide for the owner is written. To overrule: change those two lines.

## Targets missed

None.

## Not done

- **The two trials** themselves: by the task, two other builders run them next, each
  replacing its placeholder `run.py`.
- **The build's names inside assets and the vendored files in `dist/`.** Rewriting a
  module's or a worker's imports to hashed names, and the bare name `three`, is the
  skeleton batch's (item 2 of "By phase"); the task allowed a minimal build here.
- **The fakes in `wizard/tests/fakes/`** (the fake clock, the fake front server in
  JavaScript) and **the seams' modules**: the skeleton batch's.
- **The plan's and the root README's lines about the wizard having no code** (decision 13).

## For the owner to look at

- `make -C wizard test`, then `make -C wizard test-browser`: the fast suite and the first
  browser tests.
- `make -C wizard trials`: shows both placeholders saying they are placeholders.
- `wizard/trials/parts/hub-150k.stl` and `hex-spacer.stl` in any STL viewer: the hub
  should be a smooth ring with rounded edges, the spacer a round washer with a hex hole.
