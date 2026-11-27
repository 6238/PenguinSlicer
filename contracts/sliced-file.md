# Sliced file

What the slice service returns for a [plate configuration](plate-configuration.md): one
file, ready to send to the printer, and its summary. The file is what Orca Slicer exports
for a sliced plate, a `.gcode.3mf` archive. The slice service's HTTP interface serves the
file alone at `GET /slices/<job>/file`, and the summary, a JSON object, on its own at
`GET /slices/<job>/summary` ([The HTTP interface](../slice/README-details.md#the-http-interface)
in the slice service's details file). The Orca release is the one the slice service pins
([Orca Slicer](../slice/README-details.md#orca-slicer) in the same file).

This file holds two things, kept apart. [To be built](#to-be-built) is what phase 2 changes.
Every section after it is true of the code as built; where phase 2 changes one, the section
says so in its first line, and the design under To be built wins.

## To be built

*To be built in phase 2.* The routes that carry the sliced file and its summary are those of
[the slice service's HTTP interface](slice-http-interface.md#the-sliced-file), which from
phase 2 need the user key. Four things change:

- **At most 50 MB.** A sliced file larger than 52,428,800 bytes (50 MB) is never returned:
  the slice job fails with `slice.output_too_large` (stage `saving`, `retryable` false), whose
  sentence is the slice service's own and whose remedy is fewer instances or a new plate. The
  front server refuses a larger file too, as `front.sliced_file_too_large`, as a second
  defence. The largest measured is 14.1 MB.
- **The part warnings are found on upload.** `part_warnings` are those the slice service
  found on each part when it was uploaded, by itself, to the part store, each now with `where`
  naming the part as the plate configuration names it.
- **The copy is deleted once stored.** The slice service keeps a done slice job's sliced file
  only until the front server says it has stored it (`DELETE /slices/<job>/file`); then it
  deletes its copy at once, and the file and the summary answer `slice.file_gone` (HTTP 410)
  while the slice job's record lasts, two hours after it ended. A sliced file nobody collects
  goes with its record.
- **No uploads are kept with a slice job.** A slice job holds its parts by a hold on the part
  store's files for as long as it runs, and keeps none of them once it ends; the part store
  keeps each part by its own rule
  ([Keep each part once](../slice/README.md#keep-each-part-once-the-part-store)).

## Name

`<first part>[_plus<N>]-<YYYYMMDD-HHMM>.gcode.3mf`, for example
`Bracket_plus1-20261009-1432.gcode.3mf`:

- `<first part>` is the name of the part of the plate configuration's first instance,
  reduced to letters, digits, `-` and `_` (every other character becomes `_`, at most 40
  characters, `part` when nothing is left);
- `_plus<N>` is there when the instances use more than one part: `N` is the number of the
  other parts;
- `<YYYYMMDD-HHMM>` is the plate configuration's `local_time`, or the slice service's UTC time when
  `local_time` is missing or not in that form.

The name never ends in `-j` and seven or eight hexadecimal digits before the extension, so
it cannot be mistaken for a name that already carries a printer delivery's job suffix.
`GET /slices/<job>/file` offers the file under this name (its `Content-Disposition`).

## Contents

The archive is a zip. The slice service reads, and a printer delivery may rely on, these
entries:

| Entry | Meaning |
|---|---|
| `Metadata/plate_1.gcode` | The G-code of the plate. There is always exactly one plate, plate 1, and its header carries `; total layer number: <n>`. |
| `Metadata/slice_info.config` | Orca's slice summary: the predicted print time, the filament weight and length. |
| `Metadata/plate_1.json` | The objects sliced onto the plate. Its `bbox_objects` list holds one object per instance, named as the instance (`Bracket #1`), each name once and none blank. |

The profiles the plate was sliced with travel inside the archive, so a printer delivery
never needs to know the printer, filament, plate or nozzle.

## Summary

| Field | Type | Meaning |
|---|---|---|
| `file` | string | The sliced file's name (see Name), the name `GET /slices/<job>/file` offers it under. |
| `instances` | integer | The number of instances on the plate. |
| `print_time_s` | number or null | Orca's predicted print time, in seconds. |
| `filament_m` | number or null | The filament used, in metres. |
| `filament_g` | number or null | The filament used, in grams. |
| `layer_count` | integer or null | The number of layers. |
| `warnings` | array of strings | Orca's warnings for the plate, each as Orca wrote it, each once, sorted with the numbers in them read as numbers (`Block #2` before `Block #10`) so the same plate gives the same list every time; at most 300. Read from Orca's `result.json` and its debug log (the `result.json` of the pinned Orca holds only one of them). Empty when there are none. When a timeout or the memory watchdog stopped Orca after it wrote the sliced file but before it wrote `result.json`, the list holds only the warnings its debug log had by then (the slice service's log says so in `stop_note`). |
| `part_warnings` | array of objects | The slice service's own warnings about the parts, found when the plate configuration arrived (built today; phase 2 finds them when each part is uploaded, see To be built); empty when there are none. Each has `code` (for example `slice.part_not_watertight`; the guide lists them), `message` (a sentence for the user), `where` (`part`) and `detail` (the evidence for the log). |

A number Orca did not report is `null` rather than a failure: the sliced file is still
good.

## Rules

- A sliced file is returned only when Orca sliced every instance: the slice service fails
  with `slice.left_off_plate` when an instance is missing from `Metadata/plate_1.json`,
  because Orca leaves an instance that is entirely off the plate out without an error.
- A sliced file is returned only when every entry of the archive passes its checksum: a
  file Orca cut short or damaged anywhere fails with `slice.unreadable_output`.
- A complete sliced file is returned even when a timeout or the memory watchdog stopped
  Orca in the moment after it wrote the file: complete means it is under its final name,
  opens as a zip with its directory intact, has `Metadata/plate_1.gcode` and
  `Metadata/plate_1.json`, and every entry passes its checksum. A cancel discards it.
- Built today; phase 2 changes this (see To be built): a done slice job keeps only its
  sliced file and its uploaded parts on the slice service's machine, until its record
  expires ([The HTTP interface](../slice/README-details.md#the-http-interface) in the slice
  service's details file): the slice service slices in a scratch folder and removes that
  folder whether the slice succeeds or fails.

## Example

See [examples/sliced-file.json](examples/sliced-file.json), the summary the slice service
gave for [examples/plate-configuration.json](examples/plate-configuration.json).
