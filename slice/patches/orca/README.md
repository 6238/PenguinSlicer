# Patches to Orca Slicer

None is applied. `make upgrade-orca` stops when this folder holds a `*.patch` file,
because patching Orca means building it from source, which is the owner's decision and is
not done by the upgrade command. Each patch, if one is ever added, sits here as
`<orca version>-<what it does>.patch` with a section below: the gap it closes, why it
cannot be closed from outside, whether it has been offered upstream, and the test of the
upstream check (`make test-upstream`) that fails without it.

## Proposed, not made: critical warnings in result.json (Orca 2.4.2)

**The gap.** When Orca's command line refuses a plate because of a critical warning found
while slicing (for example "It seems object X has floating regions. Please re-orient the
object or enable support generation."), it exits with return code -100 and writes only its
general `error_string` ("Failed slicing the model...") into `result.json`. The real reason
reaches only Orca's debug log, at `--debug 3` or higher, as a `cli_status_callback` line.
The empty-layer refusal is not affected: Orca writes it into
`sliced_plates[].warning_message`, and the slice service reads it from there.

**Why not from outside.** The slice service could run Orca with `--debug 3 --logfile
<scratch>/orca.log` and read the `cli_status_callback ... warning_step=` lines on failure.
That was tried on a part with floating regions: it works, but at that level Orca also
writes its whole debug log (tens of kilobytes per small plate, more for large ones) on
every slice, and the format of a debug log is not something Orca promises to keep. It is
the fallback if the gap matters in practice; today such a failure is reported truthfully
but generally, as `slice.orca_failed` with Orca's own words in the detail.

**The change proposed.** In Orca's command-line slicing loop, when a plate fails after a
status callback with `message_type` 2 (critical), copy that message into the plate's
`warning_message` in `result.json`, as the empty-layer path already does. A few lines in
`src/OrcaSlicer.cpp`; worth offering upstream, since every command-line user meets it.

**The test it would turn on.** A test in `tests_orca/test_orca.py` slicing a part with a
floating region and supports off, asserting its warning reaches the error report's detail.
