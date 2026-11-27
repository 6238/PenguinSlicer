# Record of batch front-0-contract-examples

The batch writes out, as files under
[contracts/examples/wizard-front/](../../../../contracts/examples/wizard-front/README.md), the
example requests and answers that [the contract between the wizard and the front
server](../../../../contracts/wizard-front-server.md) held only inline, and links each file
from the place where its inline example stands. The contract's names, shapes and rules are
unchanged: the only change to it is the fourteen links, each added beside the text it
belongs to.

## Decisions made

1. **Which inline examples get a file.** The task says one file for each inline example and
   does not say what counts as one. I counted the eight fenced blocks that hold a request or
   an answer, and the six bodies written as JSON inside prose or a table cell that are whole
   requests, answers or messages (the sign-out answer `{}`, the `200` of
   `PUT /api/configuration`, the `200` of `/summary`, the window's `signed_in` message, and
   the bodies of the pairing and send requests). I left out the mermaid diagram, the
   `Content-Security-Policy` header value and the `<meta>` tag (a header and a fragment of a
   page, not a request or an answer), the `sliced_file` fragment of a delivery job's final
   report (it stands whole inside [printer-mine.json](../../../../contracts/examples/wizard-front/printer-mine.json)),
   and the bodies listed under Not done. To overrule: name the further ones and write them
   the same way.
2. **The file names.** Named for the request and the case, after
   [examples/slice-http/](../../../../contracts/examples/slice-http/): `slice-accepted.json`,
   `slice-done.json`, `slice-events.txt`, `part-record.json` as there; a request body ends
   `-request`. The stream is `.txt`, as `slice-http/events.txt` is. To overrule: rename the
   files and the links together.
3. **What "exactly what the inline example holds" means.** A file holds every field its
   inline example shows, with the same value; an object holds exactly the keys shown unless
   the inline object has the key `"..."`, when it may hold more; a value written `"…"`,
   `"..."` or in angle brackets is a placeholder and may be any value; a string with `…` in it
   keeps the text before the first `…` and after the last. So `slice-accepted.json` has no
   `part_warnings` in `slice`, since the inline `slice` object is closed. To overrule: the
   contract would say otherwise beside its examples.
4. **The configuration written by `PUT`.** The inline `{ "format": 1, "...": "..." }` is
   completed with [the hand-written configuration](../../../../contracts/examples/configuration-hand-written.json)
   byte for byte in content, since a write is of a group's own document, not the default.
5. **Revisions.** The contract makes `revision` an opaque marker of the state bucket and the
   front server's details make its form *proposed* (a hash of the contents for the folder,
   R2's ETag hosted). The files use opaque 16-character hexadecimal strings,
   `a41f6c2e9d0b7385` read and `c07e19b54a2d8f63` written. Nothing may parse them.
6. **The part's hash.** The inline record shows `9f2c…` for a part of 1,288 triangles in
   inches, which matches no file in `contracts/examples/parts/`. The file uses an invented
   64-character lowercase hexadecimal string beginning `9f2c`, the hash of no file;
   [report-failure-request.json](../../../../contracts/examples/wizard-front/report-failure-request.json)
   names the same hash as its `part_sha256`. To overrule: add a real part of those
   measurements and use its hash.
7. **The watertight warning's sentence.** The inline sentence ends in `…`. The file finishes
   it with the sentence the wizard's guide gives as the kind expected ("It may still slice
   and print. If the slice fails, look in your CAD program for faces that do not meet, then
   add the repaired part again."), starting "This part" as the contract does, since an upload
   carries no name. The `detail` is invented evidence (`open edges 14, separate pieces 2`); it
   says nothing of whether the surface is closed, so as not to assert in a second place what
   the record's `volume_mm3` contradicts. See Targets missed: the slice service as built words
   this warning otherwise, and the record's volume breaks a rule.
8. **The slice job's first report.** Completed from
   [slice-http/slice-accepted.json](../../../../contracts/examples/slice-http/slice-accepted.json)
   and [the phase 2 plate configuration](../../../../contracts/examples/plate-configuration-phase-2.json):
   the same `plate_id` and `submission_id`, `stage` `queued`, `elapsed_s` 0, `expected_s` 75,
   `sequence` 1, with the inline `ahead` 2. The slice job's id stays the contract's
   `3f9a1c2b`.
9. **The sliced file's details.** The inline `sliced_file` is `{"...": "..."}`. The files fill
   it by the table of [The sliced file's details](../../../../contracts/wizard-front-server.md#the-sliced-files-details):
   `summary` is [examples/sliced-file.json](../../../../contracts/examples/sliced-file.json)
   unchanged, as the contract says the summary is passed; `file` is that summary's name;
   `size_bytes` 1,843,207 is invented; the slice ended `2026-11-27T22:31:47Z` and expires two
   hours later. `expires_in_s` is 7,194 in the `done` report (answered six seconds after the
   end, while the file was stored) and 6,407 in the `/summary` answer (asked at
   `22:45:00Z`), so the two show that the figure is counted from each answer. The summary
   counts 3 instances, from the plate configuration that summary was sliced from, while
   `slice-accepted.json` names the phase 2 plate of 4: the files show shapes, not one story.
   To overrule: give the summary 4 instances, which would no longer be the slice service's
   example unchanged.
10. **The stream's reports.** The running report takes `stage_label` "Generating infill" from
    [the stages table](../../../../contracts/progress-report.md#a-slice-jobs-reports); its
    `fraction`, `elapsed_s` and `expected_s` are those of
    [examples/progress-report.json](../../../../contracts/examples/progress-report.json). The
    `done` report is that of `slice-done.json`. Each `progress` event's `id` equals its
    report's `sequence`, as the contract says. The file ends with a blank line, which ends
    the last event in server-sent events.
11. **The page's random id.** `c1e0…` is completed as a UUID,
    `c1e07b3a-5d2f-4e91-8a6c-0f3b9d27e4a1`, since the page already makes UUIDs for
    `plate_id` and `submission_id`. The contract fixes no form beyond a random id.
12. **The phase 5 answer of `/api/printer/mine`.** The delivery jobs' ids take the relay's
    present form, `j` and eight hexadecimal digits (`j5b20e7c4`, `j19a3f6b0`). The live report
    is a print at 38 percent, its fields those that
    [printer delivery's States and stages](../../../../delivery/README-details.md#states-and-stages)
    lists for `printing` (`fraction` 0.442 = 0.1 + 0.9 × 0.38, by its convention; `expected_s`
    = `elapsed_s` + 60 × `remaining_min`). The last print ended at the inline
    `2026-11-27T19:25:00Z`; with the answer at `20:10:00Z`, its sliced file expires at
    `21:25:00Z`, 4,500 seconds on. The send request names the live job's slice job,
    `5e2b8c19`. Its lengths of time are whole seconds (`elapsed_s` 1503 and 2241,
    `expected_s` 3483), by the contract's rule, since here the values were the batch's to
    choose. Phase 5 may reshape printer delivery's own fields; then this file changes with
    them.
13. **Where the links stand.** A link follows its fenced block or sentence as "See
    examples/wizard-front/<file>.", the text linked to that file; one in a table cell is put in parentheses in the cell; the
    `200` of `PUT /api/configuration`, written in a table, is linked in a line after the
    table. Each removed line of the diff comes back with only the link added.
14. **How the files are checked.** There is no `front/` project yet. A throwaway script outside
    the repository reads every inline example from the contract itself (the fenced blocks by
    their order, the others by their exact text, which must occur once) and compares each file
    by the rule of decision 3; it also checks each link stands in the section of its example
    and the folder's README lists every file. It failed with no files, passes now, and caught
    three hand mutations (a changed name, an extra key, an `id` not the `sequence`).
15. **What the folder's README warns of (second review).** The documents are silent on what
    the README says beyond listing the files. It names every file that breaks a rule of the
    contract: four, with `slice-summary.json` linked beside `slice-done.json` and
    `slice-events.txt`, the lengths of time described as "not written as whole numbers" so
    that 2145.0 is covered as well as 31.5. It also says the files show shapes, not one
    story, naming the 4 instances of the accepted plate against the 3 of the summary
    (decision 9), and calls its files requests, answers or window messages, since
    `signin-window-signed-in.json` is a message between windows. A throwaway check (the old
    "Two files" sentence present, `slice-summary.json` absent from the bullet) failed before
    the edit and passes after it. To overrule: cut the warnings, leaving the record as the
    only place they stand.

## Targets missed

- **The watertight warning's sentence disagrees with the slice service as built.** The
  contract's inline record, and so `part-record.json`, words it "This part is not watertight:
  its mesh has 14 open edges in 2 places. …"; the slice service's code words it "{name} has
  holes in its surface (… open edges, … separate pieces); if the slice fails or looks wrong,
  repair it in CAD." No suite should assert the warning's `message` equals the file until the
  slice service's builder settles the sentence for an upload, which carries no name.
- **The part's record breaks the contract's rule for `volume_mm3`.** The contract's table of
  the part's record, and the slice service's HTTP interface, say `volume_mm3` is `null` for a
  surface that is not closed. The inline record, and so
  [part-record.json](../../../../contracts/examples/wizard-front/part-record.json), gives
  `volume_mm3` 9910.4 beside a `slice.part_not_watertight` warning with 14 open edges. The
  slice service as built gives a third figure: when a part is not watertight it reports the
  bounding box's volume (`slice/src/penguin_slice/mesh.py`, `analyse`), which for
  `size_mm` [50.8, 50.8, 4.775] is 12,322.6 mm³. The file keeps the inline 9910.4, since the
  batch was to hold exactly what the inline example holds and to change no rule; the folder's
  README names the conflict. To settle it, the contract's example becomes `null` (and the file
  with it) or the rule changes, and the slice service follows whichever the contract says.
- **Lengths of time not written as whole numbers.** The contract says, under Answers, errors and
  times, that a length of time is a number of whole seconds in a field ending `_s`. The
  progress report contract types `elapsed_s` and `expected_s` as a number, and its examples
  and the slice service's (`slice-http/events.txt`, `examples/sliced-file.json`) carry
  values written with a decimal point, fractions (31.5) or not (2145.0). The front server passes the slice service's reports and summary unchanged, so the
  files keep them: `elapsed_s` 31.5 and 52.8 in
  [slice-events.txt](../../../../contracts/examples/wizard-front/slice-events.txt) and
  [slice-done.json](../../../../contracts/examples/wizard-front/slice-done.json), and
  `print_time_s` 2145.0 in the summary of both and of
  [slice-summary.json](../../../../contracts/examples/wizard-front/slice-summary.json). Where
  the values were the batch's to choose (printer-mine.json, decision 12) they are whole. To
  settle it, the contract's rule says it covers only the front server's own figures, or the
  front server rounds what it passes, which would break "unchanged".
- **No fast suite was run.** The batch has no component with a suite (`front/` does not exist
  yet); the comparison script ran in its place, before and after the fixes of the review, and
  again after merging `origin/main` into the branch, which had not moved since the branch was
  cut.

## Not done

- **The bodies written only as a reference to another answer,** all of phase 5 or 4:
  `{"printer": {…}}` of `GET /api/printer`, the `201` of pairing, the `200` of unpairing, the
  `202` of a send, the `200` of `GET /api/printer/deliveries/<delivery>`, the `200` and `202`
  of a cancel and the `200` of stop-following. Each would be invented almost whole from
  printer delivery's shapes, which phase 5 settles. The line is not clean, as the review
  noted: [printer-mine.json](../../../../contracts/examples/wizard-front/printer-mine.json)
  was invented the same way, because its inline example is a fenced block, and the `202` of
  a send is a whole answer in a table cell that decision 1's rule counts. Both stay as they
  are: phase 2 uses neither, and every inline example of phase 2 has its file. Phase 5 writes
  the rest when printer delivery's shapes are settled.
- **Declined from the review: no link from the contract to the folder's README.** The batch was told to change nothing
  else in the contract; a pointer like the one in the slice service's HTTP interface is for a
  later change.
- **Declined from the review: `examples/progress-report.json` says "Generating supports"** where the stages table says
  "Checking and generating supports". It is not this batch's file, and the batch's files take
  "Generating infill" from the table; left for the progress report contract's owner.
- **The small window's `sign_in_failed` message** (phase 4): its `report` is a
  `front.sign_in_refused` or `front.sign_in_failed` report whose sentences no document
  writes, and inventing them would settle the front server's wording.
- **`GET /api/configuration` and `POST /api/reports/drawing`** have no inline example to write
  out; their fields are tables only.

## For the owner to look at

- The folder's list: [contracts/examples/wizard-front/README.md](../../../../contracts/examples/wizard-front/README.md).
- The links in the contract:
  `git -C <worktree> diff origin/main -- contracts/wizard-front-server.md`.
