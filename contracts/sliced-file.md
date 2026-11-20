# Sliced file

What the slice service returns for a [plate job](plate-job.md): one file, ready to send
to the printer, and its summary. The file is what Orca Slicer exports for a sliced plate,
a `.gcode.3mf` archive; the summary is a JSON object. The Orca release is the one the
slice service pins ([its guide](../slice/README.md), "Orca Slicer").

## Name

`<first part>[_plus<N>]-<YYYYMMDD-HHMM>.gcode.3mf`, for example
`Bracket_plus1-20261009-1432.gcode.3mf`:

- `<first part>` is the name of the part of the plate job's first copy, reduced to
  letters, digits, `-` and `_` (every other character becomes `_`, at most 40 characters,
  `part` when nothing is left);
- `_plus<N>` is there when the copies use more than one part: `N` is the number of the
  other parts;
- `<YYYYMMDD-HHMM>` is the plate job's `local_time`, or the slice service's UTC time when
  `local_time` is missing or not in that form.

The name never ends in `-j` and seven or eight hexadecimal digits before the extension, so
it cannot be mistaken for a name that already carries a printer delivery's job suffix. The
file is written into the output directory under this name, replacing a file of the same
name.

## Contents

The archive is a zip. The slice service reads, and a printer delivery may rely on, these
entries:

| Entry | Meaning |
|---|---|
| `Metadata/plate_1.gcode` | The G-code of the plate. There is always exactly one plate, plate 1, and its header carries `; total layer number: <n>`. |
| `Metadata/slice_info.config` | Orca's slice summary: the predicted print time, the filament weight and length. |
| `Metadata/plate_1.json` | The objects sliced onto the plate. Its `bbox_objects` list holds one object per copy, named as the copy (`Bracket #1`), each name once and none blank. |

The profiles the plate was sliced with travel inside the archive, so a printer delivery
never needs to know the printer, filament, plate or nozzle.

## Summary

| Field | Type | Meaning |
|---|---|---|
| `file` | string | The sliced file's name (see Name), inside the output directory. |
| `copies` | integer | The number of copies on the plate. |
| `print_time_s` | number or null | Orca's predicted print time, in seconds. |
| `filament_m` | number or null | The filament used, in metres. |
| `filament_g` | number or null | The filament used, in grams. |
| `layer_count` | integer or null | The number of layers. |
| `warnings` | array of strings | Orca's warnings for the plate, each as Orca wrote it; empty when there are none. |

A number Orca did not report is `null` rather than a failure: the sliced file is still
good.

## Rules

- A sliced file is returned only when Orca sliced every copy: the slice service fails with
  `slice.left_off_plate` when a copy is missing from `Metadata/plate_1.json`, because Orca
  leaves a copy that is entirely off the plate out without an error.
- Nothing else is left in the output directory: the slice service works in a scratch
  folder inside it and removes that folder whether the slice succeeds or fails.

## Example

See [examples/sliced-file.json](examples/sliced-file.json), the summary the slice service
printed for [examples/plate-job.json](examples/plate-job.json).
