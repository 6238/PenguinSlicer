# Brief: the owner's feedback applied to the slice service

- **Deliverable (REQUIRED):** the changes below, in `slice/`, `contracts/`, the top-level
  `README.md` and the top-level `CLAUDE.md`, and a result file at
  `docs/orchestration/review-feedback/results/slice.md` that lists, per numbered item
  below: what was done, the test that proves it, any choice you made, and anything not
  done with the reason.
- **Stop condition (REQUIRED):** every item is done or answered; the fast suite passes 20
  times in random order with 2 workers (`make -C slice test-flakes RUNS=20 WORKERS=2`);
  branch coverage of the package is still 100%; the real-Orca suite passes; a search of
  your folders finds no old term except ones you list as deliberate.
- **Budget (REQUIRED):** 150 minutes; no cloud spend.
- **Where this fits:** a fresh reviewer who never sees your result file will check the
  work, rerun the suites, break the code on purpose and try hostile inputs.
- **Inputs:** [standing-rules.md](standing-rules.md) first. Then `slice/README.md`,
  `contracts/`, and the last review of the slice service,
  [slice-hardening-review-4.md](../../penguin-slicer/results/slice-hardening-review-4.md),
  whose "Defects" and "Open at commit" sections describe items 4 to 7 below.

Do not touch `delivery/` or `docs/` (except your result file).

## 1. The renames

Apply the four renames of the standing rules everywhere in your folders: prose, code
identifiers, file names, JSON field names, form field names, make targets, error codes
and the sentences students read. Examples: `contracts/plate-job.md` becomes
`contracts/plate-configuration.md`; the module `plate_job.py` becomes
`plate_configuration.py`; `PlateJobRefused` becomes `PlateConfigurationRefused`; the JSON
field `copies` becomes `instances`; `MAX_COPIES` becomes `MAX_INSTANCES`. Nothing outside
this repository uses these names yet, so no old name is kept as an alias. Orca's own
names for its own things stay as Orca writes them. Check each sentence a student can see
reads naturally for a part with one instance.

## 2. One interface

The owner's ruling: the HTTP interface is the slice service's one interface. In time
there may be several instances of the slice service, possibly on a machine other than the
web application's.

- Remove the `slice` command of `python -m penguin_slice`. The `serve` command stays.
  Nobody is required to slice by hand; developers write throwaway scripts against the
  HTTP interface.
- The guide documents the HTTP interface as the only way in. The Python function
  `slice_plate_job` (to be renamed under item 1) and `slicer.slice_plate` remain as code
  the HTTP interface and the tests call; the guide and the package docstring stop
  presenting them as ways in. The guide shows how to start the service and submit the
  example plate configuration with `curl`.
- A cancel always discards the file. Remove anything that exists only for the command
  line (its stop notes, its handling of Ctrl-C during a slice).
- In the top-level `CLAUDE.md`, add under the quality bar: one interface per component is
  the default, not a hard rule; the wizard may exist both inside Onshape and as a page
  reached directly from a browser, and the Onshape source may likewise have two homes.
- Also bring the top-level `CLAUDE.md` up to date: the repository is `6238/PenguinSlicer`
  on GitHub; every change reaches `main` through a pull request, never a direct commit
  or push to `main`; specs, plans, research, the mockup and build records live under
  `docs/`; and the make targets in its table match the Makefiles.

## 3. The summary leaves the header

The owner called this a design flaw: an HTTP header must not carry 10 kB or more. Add
`GET /slices/<job>/summary`, which returns the sliced file's summary as a JSON body and
gives the same error reports as the file route for a slice job that is unknown, failed,
cancelled or not finished. The file route returns only the file; the `X-Slice-Summary`
header is removed. Update the guide's route table and `contracts/sliced-file.md` if it
mentions the header.

## 4. Three small defects from the last review

- **Damage to a sliced file reported as "The slicer failed unexpectedly"** (the review's
  defect on the vaguer sentence): give it the true sentence and mark it worth retrying.
- **`slicer.slice_plate` reusing an output folder can hand back an old file after a
  stop:** remove an existing file before starting Orca.
- **A memory ceiling setting with a digit that is not a plain 0 to 9 makes every slice
  fail:** accept plain ASCII digits only, and refuse anything else at start with a
  message that names the setting.

## 5. The peak memory in the log

The logged peak can include the slice service's own memory. Take the logged peak from the
watchdog's measurement of Orca alone. If that is not possible, say why in the result file
and state the limitation in the guide.

## 6. One process per instance

The guide must say: one instance of the slice service is one process, and its slice jobs
live in that process's memory. Several instances may run, on one machine or several; a
client must keep talking to the instance that accepted its slice job. A server that
starts several worker processes for one instance loses slice jobs.

## 7. Orca's reason for a failed slice, from its debug log

The owner's ruling: no patch to Orca. When a slice fails and Orca's result file gives no
reason (the thin, tall part that fails with only "The slicer could not slice this
plate"), read the reason, for example "floating regions", from Orca's debug log.

- Keep the reading in one function at the single seam to Orca. If the log is missing,
  unreadable or has no recognisable reason, the error report keeps today's general
  sentence. It never states a reason the log does not give.
- The log format is Orca's and can change at an upgrade, so the upstream check must
  notice. Add a real-Orca test that slices a part known to fail this way and asserts that
  the reason is found. Confirm that `make upgrade-orca` runs the upstream check, so a
  changed log format fails the upgrade with a message that says what to fix. State this
  in the guide's section on taking a new Orca version.
- Remove the patch note `slice/patches/orca/README.md` and any text that proposes the
  patch. The rule that a patch to Orca is the owner's decision stays in the guide in one
  sentence.
- The guide states that the pin stays at Orca 2.4.2 and that taking 2.5.x is known
  future work, with what blocks it (the packed profile file `BBL.opc`).

## 8. One hundred small instances

The owner's ruling: a limit of 25 instances is too low. A team may print as many as 100
small spacers in a 10 by 10 grid.

- Add a reference plate: 100 instances of one hex shaft spacer in a 10 by 10 grid. The
  spacer fits a 3/8 inch hex shaft, is 1/8 inch thick, and is round outside, 5/8 inch
  across (the outside shape is the coordinator's assumption). Generate its STL in a test
  helper; do not commit a large binary.
- Measure it with the real Orca, one slice at a time: peak memory, slicing time, and the
  size of the sliced file. Then set `MAX_INSTANCES` to at least 100, at a value the
  measurements support, and record the figures in the guide where the other limits are
  explained. Remember that the memory watchdog, not the instance count, is what protects
  the machine.
- Check every limit derived from the instance count. The upload bound
  `MAX_COPIES x MAX_PART_BYTES` must not become absurd: instances of one part share one
  STL file, so bound the upload by what is actually sent.
- The fast suite covers the new limit: 100 instances accepted, one more than the limit
  refused with a true sentence.
