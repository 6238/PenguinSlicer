# Batch slice-1-parts-arrive: the user key, the part store, units and the plate configuration

The builder's record of items 1 to 4 of
[the slice service's details, Phase 2](../../../../slice/README-details.md#phase-2-one-machine):
the user key on every request, one part uploaded into the part store, units beside each
part, and the plate configuration in its phase 2 form, built to
[the slice service's HTTP interface](../../../../contracts/slice-http-interface.md) and
[the plate configuration contract](../../../../contracts/plate-configuration.md#to-be-built).
What was built is described in
[The user key, the part store, units and the plate configuration](../../../../slice/README-details.md#the-user-key-the-part-store-units-and-the-plate-configuration)
and in [the guide](../../../../slice/README.md#keep-each-part-once-the-part-store).

## Decisions made

1. **How a user key becomes a folder name in the part store** (the one decision the task
   named). The documents leave it to the builder. Chosen: the folder is the SHA-256 hash
   of the user key's UTF-8 bytes, 64 lowercase hexadecimal characters
   (`part_store.user_folder`). Reason: a hash never holds `/`, `..` or a NUL, is never empty
   or too long for a file system, so no user key can name a path outside its own folder; two
   different user keys share a folder only through a collision of SHA-256; and the same key
   gives the same folder in every process with no table to keep, so it survives a restart.
   The tests try `../../etc`, `/`, the empty string, `\0`, a 10,000-character key and
   unpaired surrogates. To overrule: change `user_folder`; since the part store is emptied
   at every start, no folder needs moving.
2. **Where the part store lives, and how a start empties it.** The details file says it is
   "emptied when the slice service starts, beside `service.clean_stale_scratch`". Chosen: each
   slice service process makes a new folder for it, named like its scratch
   (`slice-<pid>-<start>-parts-<random>`), and `clean_stale_scratch` removes the folder of a
   process that is no longer running. Reason: two processes that share a work folder (tests,
   or a restart that overlaps the old process) never empty each other's part store. To
   overrule: one fixed folder, removed whole by `create_app`.
3. **The limit on disk: its name, figure and form.** The details file proposed the name
   `PENGUIN_SLICE_PART_STORE_MAX_MB` and left the figure to the builder. Chosen: that name,
   1,024 MB by default, whole megabytes of 1 to 7 plain digits, at least 8 (room for one
   part of the largest size), refused at start like the memory ceiling. Reason: on one
   machine 1,024 MB holds about 140 parts at the size limit and thousands of ordinary ones,
   about five full plates of the largest parts. To overrule: change `DEFAULT_MAX_MB`; the
   slice container's figure waits for the disk measurement anyway.
4. **The two hours and their sweep.** Kept the proposed `PART_STORE_TTL_S` (7,200 s). The
   documents say the job pool's sweeper removes expired parts; chosen: `JobPool.start_sweeper`
   takes `also=(store.sweep,)` and calls it after each sweep of slice jobs, rather than a
   second thread.
5. **A slice job's hold on a part.** Proposed as a hard link. Chosen: a hard link into the
   slice job's folder (`parts/<sha256>-<units>.stl`), a copy where the file system refuses
   hard links, taken under the part store's lock. A part removed between the checks and the
   hold makes it missing (`slice.part_missing` with `missing_parts`) and nothing is held.
6. **The least recently used part, and the part just added.** Silent on whether a part just
   uploaded may itself be pushed out. Chosen: never the part just added, even with a clock
   that went back.
7. **The sentences of an upload.** An upload carries no name. The front server's contract
   shows warnings that begin "This part ..."; silent on the sentences that begin "The file
   for {name}". Chosen: every sentence of the checks is formed with "this part" and its
   first letter capitalised ("This part is too small to print ...", "The file for this part
   is empty."), and the refusal's `where` names no part. The over-size refusal is exactly
   the contract's example.
8. **The largest printer of the profile catalog.** Silent on what "largest" means when
   printers differ in width, depth and height. Chosen: the envelope (the widest, the deepest
   and the tallest, over the default printer and every catalog printer), so the fit test on
   arrival stays a necessary one. Today every printer is 340 x 320 x 340 mm. A part refused
   on arrival gets a sentence of its own: "This part is ... mm, larger than any printer here
   can print in any orientation (the largest prints 340.0 x 320.0 x 340.0 mm)." To overrule:
   change `service._largest_plate`.
9. **A repeated upload is not checked again.** The contract says the same bytes answer the
   same record and count as a use. Chosen: the hash is taken first, and a part already held
   under the same user key and units is answered from what its first upload found, with 201
   like the first. Reason: the checks are deterministic, and a 150,000-triangle part takes
   a tenth of a second to check.
10. **The order of an upload's refusals.** Silent. Chosen: the user key, then the units, then
    a missing Content-Length, then a Content-Length over the cap, then the checks on the body.
11. **The sentences of the two new codes.** `slice.no_user_key` is the contract's example,
    word for word. `slice.bad_units` (the contract fixes only the code): "The slicer was not
    told whether this part is in millimetres or inches.", remedy "Choose millimetres or inches
    for the part and add it again.", stage `checking`, not retryable, no action, detail
    "no units label" or "units 'cm', not 'mm' or 'in'". An upload without a Content-Length is
    `slice.bad_request` with "The slicer was not told how large this part is."
12. **A plate configuration sent without a Content-Length.** The contract fixes the refusal
    before reading for a Content-Length over 1 MB. Chosen: a body without one is read no
    further than `web.MAX_BODY_BYTES` (7,500,084 bytes, Flask's own limit) and refused for its
    size (413) when it is over 1,048,576 bytes. Flask's own 413 handler was removed, since no
    request reaches it.
13. **What counts as "not JSON".** Chosen: only a multipart body is refused for its type;
    any other body is parsed as JSON, whatever its Content-Type, and refused (400, "it is not
    JSON") when it does not parse.
14. **The overrides stay the four as built until item 6.** Item 4's field list includes
    `overrides` under Orca's own names, but checking those is item 6, which rests on the
    table of settings of item 5. Chosen: `overrides` keep `print_config.OVERRIDE_CHOICES`
    (`infill`, `walls`, `supports`, `brim`); the tests send the contract's phase 2 example,
    and the shared plates, with their `overrides` turned into those four on the way in. Reason:
    an interim checker under Orca's names would be thrown away by item 6 a batch later. To
    overrule: accept the five Orca names of the quick changes with the old lists of values in
    `print_config.validate_overrides` before item 6.
15. **The sentence for one missing part, and the remedy.** The contract's example gives
    "The slicer no longer has 2 of this plate's parts." and the remedy "Add the parts again
    and slice again.". Chosen: "The slicer no longer has one of this plate's parts." for one,
    and that remedy for every report with `missing_parts`; an instance naming no key of
    `parts` keeps the remedy as built ("Load the parts again and send a new slice.").
16. **The order inside step 4.** Chosen: an instance whose `ref` names no part is refused
    first (as built, no `missing_parts`), then every missing part of those an instance names
    is listed, in the order of `parts`; a part no instance names is not looked for, as the
    contract says only parts an instance names are read. Then each found part is tested
    against the plate's printer.
17. **A rotation in the code.** Chosen: the rotation is divided by its length and kept so in
    the checked instances (the log line shows the divided one); a part's footprints are kept
    under each instance's turn (`plate.turn_of`: the orientation's name, or the rotation as a
    tuple), so one function places both forms; the part's file is read once for all its
    rotations; a file gone from the part store meanwhile makes the part missing. A
    `rotation` whose elements are booleans is refused, as a coordinate that is a boolean is.
18. **`Cache-Control: no-store` on every answer.** The contract's rules ask for it; as built
    only the progress stream carried it. Chosen: every answer carries it now.
19. **The log lines of this batch.** Item 16 builds the log route; this batch only needed its
    own refusals logged. Chosen: every upload leaves a `part_upload` line (`stored`,
    `stored_again` or `refused`); a request without the user key, and one about another user
    key's slice job, leave a `slice_http_refused` line; every slice job line and every refusal
    of `POST /slices` carries `user_key` (cut to 200 characters), `plate_id` and
    `submission_id`; a refusal's `uploads` gave way to `bytes`. No part's bytes are logged.
20. **The form before phase 2 is gone from the code, not kept beside it.** The multipart
    route, the part's `stl` and `service.load_plate_configuration` are removed;
    `service.slice_plate_configuration` now takes a checked plate configuration. Reason: the
    details file says these are replaced, and nothing else calls the slice service yet. The
    tests that wrote plates with `stl` now upload their parts first (`helpers.Parts`).
21. **The contracts' sections on the form before phase 2.** Silent on what becomes of them
    once phase 2's form is built. Chosen: kept, each with a first line saying the slice
    service no longer reads that form or what of the section is built; the old example
    `examples/plate-configuration.json` is kept, since the sliced file's example was made from
    it, and the tests send it with its parts named by hash. Reason: the front server's builder
    may be editing the same contract; folding the two halves is a larger change best made once
    phase 2's contract work is done. To overrule: fold "To be built" into the body and delete
    the old sections and example.
22. **The upstream check's rotation.** The contract example's rotation turned out to lay the
    bracket where the pinned Orca refuses to slice it (see Targets missed). Chosen: the new
    real-Orca test lays the bracket by a `rotation` on a face of the part itself (its `-x`
    face down, then 30 degrees about the vertical, at `angle` 15) and adds a 1 x 1 x 0.5 inch
    block, and checks Orca's first layer of each against the slice service's footprint
    within the 1 mm the real parts use: 0.59 mm and 0.40 mm were measured.
23. **A user key is compared exactly.** Only a missing or empty header is refused; a key of
    spaces is a key like any other, and none is trimmed or folded in case.
24. **The two upload failures that share a code with a slice's failure have remedies of their
    own** (after review). The documents fix the codes (`slice.scratch_unwritable` for a part
    store that cannot be written, `slice.bad_request` for an upload without a
    Content-Length) and are silent on their remedies; the codes' defaults said "ask a mentor"
    and "slice again", wrong words and the wrong action on the Parts step. Chosen:
    "The slicer could not keep this part." with "Add the part again in a few minutes; if it
    fails again, the server needs more free disk space.", and "Add the part again; if it
    happens again, the server needs fixing." (the words of `slice.no_user_key`'s remedy, the
    other fault of the front server's). Their stage (`building`, `fetching`) and retryable
    flag stay the code's, as the details file's table of codes fixes one stage per code. Both
    remedies now live in `service.UPLOAD_REMEDIES` (decision 26). To overrule: change their
    entries there and in `tests/test_errors.py` (`UPLOAD_ANSWERS`); a stage of their own would
    need a change to that table and to `errors.CODES`.
25. **Two first uploads of the same bytes under one user key at once** (after review): the
    documents are silent. Both still run the checks (no lock is held across a part's check);
    `PartStore.put` keeps an entry already under the three, as a use, instead of replacing
    it, so a slice job that found the first entry can still hold it. After the second review
    `put` answers (the entry, whether it is new), so the second of the two is logged
    `stored_again`, not `stored`. To overrule: drop that early return in `put` and its test.
26. **Every refusal of an upload says what to do on the Parts step** (after the second
    review). The guide's row "A part cannot be used" says the user exports the part again or
    simplifies it, on the Parts step, and the part is not added; the details file and
    `errors.CODES` gave the part checks' codes a slice's remedies ("... and slice again", "...
    and send a new slice", `refresh_parts` on `slice.part_unreadable`), and
    `slice.profile_unreadable` "Ask a mentor ...; `make upgrade-orca` ...". The guide is right.
    Chosen: one table, `service.UPLOAD_REMEDIES`, holds the remedy of every code `POST /parts`
    can answer (`no_user_key`, `bad_units`, `bad_request`, `part_too_detailed`,
    `part_unreadable`, `part_not_binary`, `part_too_small`, `part_no_volume`,
    `part_too_large`, `scratch_unwritable`, `profile_unreadable`, `unexpected`), each about
    adding the part ("Export the part again as an STL and add it again.", "Check the part's
    units and size, and add it again.", "... and add the pieces." for a part too large), and
    an upload's report carries no `action`, since none of the contract's actions applies to a
    part never added. `service.check_part` sets the remedy on the checks' `MeshError` and on
    the `ProfileError` of the server's own profiles, whose upload sentence becomes "The slicer
    could not read its printer settings, so it could not check this part." (the slice's
    sentence names "this printer", which an upload has not chosen); `web._for_upload` sets it
    on every other answer of the route, a bug's and Flask's own among them. Covering Flask's
    own showed one more wrong sentence: a body cut off before its Content-Length answered
    "The print server does not offer POST /parts."; it now says "This part did not arrive
    whole.", under `slice.bad_request` (the contract lists 400 `slice.bad_request` for an
    upload's fault of the front server's). `errors.CODES`
    keeps the slice's remedies for the same codes, which a part read again for a plate can
    still raise (`slice.part_too_large` against the plate's own printer).
    `tests/test_errors.py` produces every code through the HTTP interface and asserts the
    remedy, no action, and no "mentor", "print server" or "slic" in any remedy. To overrule:
    change `UPLOAD_REMEDIES` and `UPLOAD_ANSWERS` together.
27. **The contract's over-size example changes its remedy** (with decision 26). The contract
    requires the 413 of an upload over 7,500,084 bytes to be exactly
    [examples/error-report-part-over-size.json](../../../../contracts/examples/error-report-part-over-size.json),
    whose remedy ended "and slice again.". Chosen: the example now ends "and add it again.";
    the code, the message and the shape are unchanged. The front server's stand-in reads the
    file, so it follows; no other component quoted the sentence. To overrule: put the old
    words back in the example and give `slice.part_too_detailed` its slice remedy on upload.
28. **A slice job's hold refuses an entry replaced under the same three** (minor finding of
    the second review). `PartStore.hold` compares each entry with the very object in the
    store; a test now sweeps an entry, uploads the same bytes again and holds the old entry:
    `PartsGone`. Reason: the slice job's use renewed the old entry, not the new one, so the
    new one could be swept under it; the plate is then answered with the part missing and
    the wizard uploads it again. To overrule: compare with `is None` and drop that test.

## Targets missed

1. **The contract's phase 2 example is not accepted as written.** Its `overrides` use Orca's
   own names (`sparse_infill_density`, `wall_loops`, `enable_support`, `brim_type`), which the
   code as built refuses with `slice.bad_overrides` until item 6 (decision 14). With its
   overrides in the four as built it is accepted; the shared plates likewise.
2. **The 202 answer's first progress report has no `ahead`** (item 8), so it equals
   [the contract's example](../../../../contracts/examples/slice-http/slice-accepted.json) in
   its fields and in `plate_id`, `submission_id` and `part_warnings`, not in `progress`.
3. **The contract example's rotation does not slice.** Its fourth instance lays the bracket on
   the face of its convex hull across the L's open corner, which is no face of the part, so
   the bracket touches the plate along two edges. The pinned Orca fails that plate (-100;
   "It seems object Bracket #3 has floating regions" in its log with supports off, its
   general reason only with supports on, the instances moved 12 mm apart), while the
   placement check accepts it. The shared rotation plates use the same face and are only
   checked, never sliced. This bears on the wizard's laying a part on any face of its hull.
4. **The part store's limit on disk was chosen without a measurement** (1,024 MB, decision 3);
   the disk the part store takes was not measured.
5. **Not every test was written before its code and seen to fail.** The scale, the rotation's
   matrix and footprint, and the part store's module were written before most of their
   tests. In their place, four checks were broken by hand and the suite run: the user key used
   as its own folder name (16 tests fail), the user key's check on a slice job removed (6
   fail), the rotation's tolerance made 1e-2 (3 fail), the scale of a part in inches dropped
   from the plate written for Orca (1 fails). The review found a fifth that survived:
   hashing only the first 100 characters of a user key passed all 1,193 fast tests. Four
   tests now fail on it, one of them a sweep of one long user key's part that leaves
   another's, differing only in its last character, unable to be held.
6. **One test waits on a real thread.** `test_the_sweeper_sweeps_the_part_store` starts the
   pool's sweeper on its own thread and waits on an event (behind the 10 s failsafe). After
   review its interval is 0, as `tests/test_jobs.py` uses, so no real interval passes; the
   wait is on the thread, not on a fake clock.
7. **The user key is not yet on every log line**: on the lines of this batch only, until item
   16 puts it on all.

## Not done

1. Comparing `plate_id` and `submission_id` among one user key's slice jobs (the repeat and
   the replacement): item 7. Both are required, checked, answered and logged.
2. The routes that answer for the whole slice service (`GET /slices`, `GET /settings-table`,
   `GET /log`) and `DELETE /slices/<job>/file`: items 5, 10, 11 and 16.
3. Folding the plate configuration contract's phase 2 sections into its body, and retiring
   its form before phase 2 and the old example (decision 21).
4. The words of the slice service's older sentences ("ask a mentor", "the print server"):
   known future work, as the details file says. As first pushed, this record said the new
   sentences of this batch used neither; that was false (the part store's refusal said "The
   print server could not keep this part." and carried the default remedy "Ask a mentor
   ..."). After the first review the batch's own two sentences used neither (decision 24),
   but the second review found that every other refusal of an upload still carried a
   slice's remedy, and `slice.profile_unreadable` "Ask a mentor"; after the second review
   no remedy `POST /parts` answers says mentor, print server or slice (decision 26). The
   older sentences of a slice, the 404 and 405 sentence ("The print server does not offer
   ...") among them, keep the old words; on `POST /parts` an error of Flask's own answers
   with the upload's sentence and remedy instead.
5. Measuring the disk the part store takes: open in the guide's Unmeasured, before phase 3.

## Findings of the reviews declined

1. First review: a refusal of a path other than `POST /slices` and `POST /parts` (a 404 or
   a 405, `GET /parts` for one) still writes no log line. That is the details file's later
   item: item 9 of "Phase 3: hosted on Railway" (the log's new lines) says that as built
   only the refusals of `POST /slices`, of `POST /parts`, of a request without the user key
   and of another user key's slice job are logged, and makes "a line for every exception
   and every refusal, whichever route it comes from" that item's work. The test that pins
   it, `test_a_method_parts_does_not_take_is_no_upload`, changes with that item.
2. First review, minor finding 1 (tests not written first) needs no change: it is Targets
   missed 5, and the reviewer's mutations there were caught.
3. Second review: none declined. Its minor finding 4 (the `errors.py` docstring said "for the
   student") was fixed with the same words in `mesh.MeshError` and
   `print_config.ProfileError`.

## For the owner to look at

- The real-Orca finding (Targets missed 3): a bracket laid on a face of its hull that is not
  a face of the part. To see it, with Orca installed (`make -C slice install`), run the
  phase 2 example through the HTTP interface with the upstream check's helper:
  `flock /var/tmp/penguin-locks/real-orca.lock slice/.venv/bin/python -m pytest -s
  "slice/tests_orca/test_orca.py::test_a_rotation_and_a_part_in_inches_slice_where_the_checks_place_them"`
  prints the first-layer errors of the bracket laid on a real face and of the inch block;
  replacing that test's rotation with the example's own gives the failure.
- The part store's rules and the user keys' folders, through the HTTP interface:
  `slice/.venv/bin/python -m pytest -q slice/tests/test_part_store.py slice/tests/test_web.py`.
- By hand, with the curl lines of [Use](../../../../slice/README-details.md#use): upload a
  part twice under `mm` and once under `in`, and look at the three records; send a request
  without `X-Penguin-User-Key` and read the refusal.
- The fast suite and its branch coverage: `make -C slice test` and `make -C slice coverage`
  (100%).
